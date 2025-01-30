import asyncio
import logging
from logging import Formatter, StreamHandler, getLogger
from typing import Annotated, Any, Callable, Literal

import chromadb
from browser_use import Agent, Browser, BrowserConfig, Controller
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.globals import set_debug, set_verbose
from langchain_chroma import Chroma
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel, Field

from src.prompt_define import assist_prompt_txt
from src.utils.browser_util import get_devtools_url, start_chrome

load_dotenv()

DEBUG = False
set_debug(DEBUG)
set_verbose(DEBUG)

# ログの設定
if __name__ == "__main__":
    logger = getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler_format = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    stream_handler = StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(handler_format)
    logger.addHandler(stream_handler)
else:
    logger = getLogger("__main__")
    logger.setLevel(logging.WARNING)


def create_browser() -> Browser:
    return Browser(
        config=BrowserConfig(
            headless=False,
            chrome_instance_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        )
    )


# 入力形式を定義
class TalkInput(BaseModel):
    name: str
    input: str


# TalkModelの出力形式を定義
class TalkFormat(BaseModel):
    reply: str = Field(..., description="視聴者に対する返答")
    action: Literal["Nothing", "Think", "WebSearch"] = Field(
        ..., description="次の行動．以下のいずれかから選択: Nothing, Think, WebSearch"
    )
    emotion: Literal[
        "normal", "happy", "angry", "sad", "surprised", "shy", "excited", "smug", "calm"
    ] = Field(..., description="現在の感情")


# ThinkModelをtoolとして定義
@tool
async def think(input: Annotated[str, "what to think about"]) -> Any:
    """Think about the input."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            gemini_think = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-thinking-exp-1219", temperature=0.7
            )
            # ThinkModelの設定
            think_prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessage(
                        content="""
            Think deeply about the input and generate an appropriate response.
            """
                    ),
                    MessagesPlaceholder(variable_name="messages"),
                ]
            )
            think_model = think_prompt | gemini_think
            message = [HumanMessage(content="Input: " + input)]

            response = await think_model.ainvoke({"messages": message})
            return response.content
        except Exception as e:
            logger.error(f"Error in think: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2**attempt)
                continue
            else:
                raise e


# WebSearchModelをtoolとして定義
@tool
async def web_search(input: Annotated[str, "what to search for"]) -> Any:
    """Search the web for the input."""
    browser = create_browser()
    model = ChatOpenAI(model='gpt-4o')
    agent = Agent(
        task=input,
        llm=model,
        controller=Controller(),
        browser=browser,
    )
    result = await agent.run()
    return result


def web_search_creater(browser_port: int) -> Any:
    browser = Browser(config=BrowserConfig(cdp_url=get_devtools_url(browser_port)))
    config = BrowserContextConfig(
        browser_window_size={'width': 300, 'height': 400},
    )
    context = BrowserContext(browser=browser, config=config)

    @tool
    async def _web_search(input: str) -> Any:
        agent = Agent(
            task=input,
            llm=ChatOpenAI(model='gpt-4o'),
            browser_context=context,
        )
        result = await agent.run()
        return result

    return _web_search


class AiAgent:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        response_callback: TalkFormat | None = None,
        tool_list: list = [],
    ) -> None:
        self.name = name
        # パラメータ設定
        # レートリミットが厳しかったので，gemini-1.5-flashを使用
        gemini_flash = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)
        self.message_history: BaseMessage = []
        self.mh_limit = 10  # 10なら対話5回分の履歴を保持
        self.session_id = "ai-tuber"
        # vector_retrieverの設定
        self.setting_vr = self._create_vector_retriever(
            top_k=1, path=f"./chroma-db-setting{self.name}"
        )
        self.memory_vr = self._create_vector_retriever(
            top_k=3, path=f"./chroma-db-memory{self.name}"
        )

        # コールバック関数
        self.response_callback = response_callback

        # setting.txtのデータをvector_retrieverに追加
        with open("./text_data/setting.txt", "r", encoding='utf-8') as f:
            setting_texts = f.read().splitlines()
            self._add_data_to_vr(self.setting_vr, setting_texts)
        # memory.txtのデータをvector_retrieverに追加
        with open("./text_data/memory.txt", "r", encoding='utf-8') as f:
            memory_texts = f.read().splitlines()
            self._add_data_to_vr(self.memory_vr, memory_texts)
        # TalkModelの設定
        talk_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=system_prompt),
                MessagesPlaceholder(variable_name="history"),
                MessagesPlaceholder(variable_name="message"),
            ]
        )
        self.talk_model = talk_prompt | gemini_flash.with_structured_output(TalkFormat)
        # AssistModelの設定
        assist_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=assist_prompt_txt),
                MessagesPlaceholder(variable_name="input"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )
        self.assist_model = AgentExecutor(
            agent=create_tool_calling_agent(gemini_flash, tool_list, assist_prompt),
            tools=tool_list,
        )
        # state graphを作成
        workflow = StateGraph(MessagesState)
        workflow.add_node("talk", self.call_talk_model)
        workflow.add_node("assist", self.call_assist_model)
        workflow.add_edge(START, "talk")
        workflow.add_conditional_edges("talk", self.talk_cond_func)
        workflow.add_edge("assist", "talk")
        self.graph = workflow.compile()
        logger.info("AItuber initialized.")

    def _add_history(self, message: BaseMessage) -> None:
        if len(self.message_history) >= self.mh_limit:
            self.message_history.pop(0)
        self.message_history.append(message)

    def _get_history(self, length: int = 4) -> str:
        msgs = self.message_history[-length:]
        return "\n".join([msg.content for msg in msgs])

    def _create_vector_retriever(
        self, top_k: int = 5, path: str = "./chroma-db"
    ) -> Chroma:
        embeddings = HuggingFaceEmbeddings(
            model_name="sbintuitions/sarashina-embedding-v1-1b"
        )
        client = chromadb.PersistentClient(path=path)
        vector_store = Chroma(
            collection_name="ai-tuber", embedding_function=embeddings, client=client
        )
        vector_retriever = vector_store.as_retriever(search_kwargs={"k": top_k})
        return vector_retriever

    def _add_data_to_vr(
        self, vector_retriever: Chroma, texts: str | list, metadata: Any = None
    ) -> None:
        if not texts:
            return
        if not isinstance(texts, list):
            texts = [texts]
        vs = vector_retriever.vectorstore
        ids = [f"doc_{i}" for i in range(len(texts))]
        vs.add_texts(
            texts=texts, ids=ids, metadatas=metadata if metadata else [{}] * len(texts)
        )

    # TODO: ENDを型アノテーションで扱う方法を調査
    def talk_cond_func(self, state: MessagesState) -> Literal["assist"] | Any:
        last_message = state['messages'][-1].content
        last_message = TalkFormat.model_validate_json(last_message)
        logger.info(f"action: {last_message.action}")
        if last_message.action == "Think" or last_message.action == "WebSearch":
            return "assist"
        return END
        # return "manager"

    async def call_talk_model(self, state: MessagesState) -> dict:
        last_msg = state['messages'][-1].content
        input = TalkInput.model_validate_json(last_msg)
        logger.info(f"{input.name}: {input.input}")
        input.input = input.input.replace("\n", "")
        setting_docs = self.setting_vr.invoke(input.input)
        memory_docs = self.memory_vr.invoke(input.input)
        setting = "\n".join([doc.page_content for doc in setting_docs])
        memory = "\n".join([doc.page_content for doc in memory_docs])
        history = self.message_history
        if not history:
            history = [HumanMessage(content="No conversation history")]
        message = [
            HumanMessage(
                content=f"setting: <{setting}>\nmemory: <{memory}>\nname: {input.name}\ninput: {input.input}"
            )
        ]
        input_message = {"message": message, "history": history}

        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = self.talk_model.invoke(input_message)
                break
            except Exception as e:
                logger.error(f"Error in talk: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                else:
                    raise e

        assert response is not None
        self._add_history(HumanMessage(content=f"{input.name}: {input.input}"))
        self._add_history(AIMessage(content=f"{self.name}: {response.reply}"))
        logger.info(f"{self.name}: {response.reply}")
        save_data = f"{input.name}: {input.input} {self.name}: {response.reply}\n"
        self._add_data_to_vr(self.memory_vr, [save_data])
        with open("./text_data/memory.txt", "a", encoding="utf-8") as f:
            f.write(save_data)
        response = response.model_dump_json()

        # コールバック関数が設定されている場合は実行
        if self.response_callback:
            self.response_callback(response)

        return {"messages": [response]}

    async def call_assist_model(self, state: MessagesState) -> dict:
        conversation = self._get_history(length=2)
        last_message = state['messages'][-1].content
        last_message = TalkFormat.model_validate_json(last_message)
        input = {
            "input": [
                HumanMessage(
                    content=f"tool: {last_message.action}\nconversation: {conversation}"
                )
            ]
        }
        response = await self.assist_model.ainvoke(input)
        talk_input = TalkInput(
            name=last_message.action, input=response["output"]
        ).model_dump_json()
        return {"messages": [talk_input]}
