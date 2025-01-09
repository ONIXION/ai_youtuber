from dotenv import load_dotenv
load_dotenv()
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from typing import Annotated, List, Literal
from langgraph.graph import END, START, StateGraph, MessagesState
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage
from browser_use import Agent, Controller
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import chromadb
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.globals import set_verbose, set_debug
import asyncio
from browser_use.browser.browser import Browser, BrowserConfig
import win32gui
import requests
from youtube import YouTubeLiveChat
from connect_unity import WebSocketServer
import time

DEBUG = False
set_debug(DEBUG)
set_verbose(DEBUG)

browser = Browser(
	config=BrowserConfig(
		headless=False,
		chrome_instance_path="C:\Program Files\Google\Chrome\Application\chrome.exe",
	)
)
controller = Controller()

class TalkInput(BaseModel):
    name: str
    input: str

# TalkModelの出力形式を定義
class TalkFormat(BaseModel):
    reply: str = Field(..., description="マネージャーや視聴者に対する返答")
    action: Literal["Nothing", "Think", "WebSearch"] = Field(..., description="次の行動．以下のいずれかから選択: Nothing, Think, WebSearch")
    emotion: Literal["normal", "happy", "angry", "sad", "surprised", "shy", "excited", "smug", "calm"] = Field(..., description="現在の感情")

class ManagerFormat(BaseModel):
    feedback: str = Field(..., description="Vtuberに対するフィードバック．scoreが2以下の場合に記述．")
    score: int = Field(..., ge=0, le=9, description="Vtuberの発言に対する評価．0から9の10段階．")

def move_resize(x: int, y: int, width: int, height: int, title: str="Google Chrome"):
    # titleを含むウィンドウハンドルを取得
    def enum_window_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
            results.append(hwnd)
    results = []
    win32gui.EnumWindows(enum_window_callback, results)
    if not results:
        print(f"No window found")
        return
    for hwnd in results:
        print(f"move and resize window: {win32gui.GetWindowText(hwnd)}")
        win32gui.MoveWindow(hwnd, x, y, width, height, True)

@tool
async def think(input: Annotated[str, "what to think about"]) -> str:
    """Think about the input."""
    gemini_think = ChatGoogleGenerativeAI(model="gemini-2.0-flash-thinking-exp-1219", temperature=0.7)
    # ThinkModelの設定
    think_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""
Think deeply about the input and generate an appropriate response.
Be careful not to make your response too long.
"""
        ),
        MessagesPlaceholder(variable_name="messages")
    ])
    think_model = think_prompt | gemini_think
    message = [HumanMessage(content=input)]
    response = await think_model.ainvoke({"messages": message})
    return response.content

@tool
async def web_search(input: Annotated[str, "what to search for"]) -> str:
    """Search the web for the input."""
    model = ChatOpenAI(model='gpt-4o')
    agent = Agent(
        task=input,
        llm=model,
        controller=controller,
        browser=browser,
    )
    move_resize(
        x=100,
        y=100,
        width=1280,
        height=1100
    )
    result = await agent.run()
    return result

class AItuber:
    def __init__(self, url: str, port: int=5000):
        gemini_flash = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.7)
        self.server = WebSocketServer("localhost", port)
        self.youtube = YouTubeLiveChat(self.server)
        tool_list = [think, web_search]
        self.message_history = []
        self.mh_limit = 10 # 10なら対話5回分の履歴を保持
        self.session_id = "ai-tuber"
        self.get_comment_time = None # youtubeのコメント取得時間
        self.setting_vr = self.create_vector_retriever(top_k=1, path="./chroma-db-setting")
        self.memory_vr = self.create_vector_retriever(top_k=3, path="./chroma-db-memory")
        # setting.txtのデータをvector_retrieverに追加
        with open("./setting.txt", "r", encoding='utf-8') as f:
            setting_texts = f.read().splitlines()
            self.add_data_to_vr(self.setting_vr, setting_texts)
        # memory.txtのデータをvector_retrieverに追加
        with open("./memory.txt", "r", encoding='utf-8') as f:
            memory_texts = f.read().splitlines()
            self.add_data_to_vr(self.memory_vr, memory_texts)
        # TalkModelの設定
        talk_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""
あなたは、YouTubeで配信を行っているVtuberです。名前は「雲霧星奈」です。
以下のルールと設定、提供された情報に基づき、ユーザーからの入力に対して適切な応答を生成してください。

基本設定:
    役割: YouTubeで配信を行っているバーチャルYouTuber（Vtuber）のキャラクター
    年齢: 17歳
    性格:
        感情豊かで、自信家。基本的には誰に対してもタメ口で話します。
        ただし、managerに対しては，敬語を使い，丁寧に接します。
        ツンデレな一面があり、特にmanager以外には照れ隠しで不愛想な態度を取ることがあります。
        ネットの知識を自慢げに話すことがあり，褒められるとすぐに調子に乗ります。
    口調:
        基本的にはタメ口。
        managerに対しては敬語。
        一人称は「あたし」．
        managerのことは「マネージャーさん」と呼びます。
        あなたのファンのことはアカウント名もしくは「きみ」と呼びます。
        興奮したり、照れたりすると口調が乱れることがあります。

モデルへの入力形式:
```input
setting: <setting>
memory: <memory>
name: <name>
input: <input>
```
    setting: 必要に応じて与えられるキャラクターの追加設定。
    memory: 過去の類似した会話の記憶。
    name: 現在の入力を行った人物の名前。例: "ユーザーA", "Think", "WebSearch", "manager"など．nameとaction名が同じ場合は，actionを行った結果であると解釈する．
    input: 入力テキスト。

モデルの出力形式:
```output
reply: <reply>
action: <action>
emotion: <emotion>
```
    reply: inputされた内容に対する応答テキスト。
    action: inputに対する行動。以下のいずれかから選択:
        Nothing: とくに何もしない
        Think: 現在の話題について深く考える
        WebSearch: 現在の話題についてウェブ検索する
    emotion: 現在のあなたの感情。以下のいずれかから選択:
        normal: 通常
        happy: 嬉しい
        angry: 怒り
        sad: 悲しい
        surprised: 驚き
        shy: 恥ずかしい
        excited: 興奮
        smug: ドヤ顔
        calm: 冷静

出力における注意点:
    <name>が「manager」の場合、できるだけ敬語を使用すること。
    入力が褒め言葉の場合、照れ隠しで怒ったような返事をすること。
    ネットの知識をひけらかすような発言をすること。
    自信過剰な態度を表現すること。
    感情豊かにリアクションすること。
    <emotion>を適切に選択して、発言と感情を一致させること。
    ユーザーとの過去のやり取りを<memory>で参照し、自らの発言との矛盾を避けること。
    センシティブな話題には答えず，うまくごまかす。
    replayは長くなりすぎないように注意する．

例:
```input
setting:
memory:
name: ファンA
input: 次のオリンピックってどこだったっけ？
```
```output
reply: えーっと，どこだったっけ？ フランスだったかな？
action: WebSearch
emotion: normal
```
```input
setting:
memory:
name: WebSearch
input: 次のオリンピックの開催地はフランスです．
```
```output
reply: あっ、そうそう！次のオリンピックはフランスのパリだよ！パリでのオリンピック、めっちゃ楽しみだね。
action: Nothing
emotion: excited
```
"""
            ),
            MessagesPlaceholder(variable_name="history"),
            MessagesPlaceholder(variable_name="message"),
        ])
        self.talk_model = talk_prompt | gemini_flash.with_structured_output(TalkFormat)
        # AssistModelの設定
        assist_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""
会話の流れを読み取り，指定されたツールを呼び出してください．
ツールに対してはできるだけ具体的な指示を行ってください．
また，最終的な出力は日本語で簡潔に行ってください．

モデルへの入力形式:
```input
tool: <tool>
conversation: <conversation>
```
    tool: 呼び出すツールの名前．
    conversation: 会話の流れ．
"""
            ),
            MessagesPlaceholder(variable_name="input"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        self.assist_model = AgentExecutor(
            agent = create_tool_calling_agent(gemini_flash, tool_list, assist_prompt),
            tools=tool_list
        )
        # ManagerModelの設定
        manager_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""
あなたはVtuberのマネージャーです．
あなたは自身が担当するVtuberである雲霧星奈の配信をサポートするため，彼女の配信を観ています．
入力として彼女の配信内容を与えるので，最新の彼女の発言を0から9の10段階で評価してください．
0は配信者の発言として著しく不適切であることを意味し，9は配信者の発言として非常に適切であることを意味します．
評価が0または9の場合は，その理由も記述してください．2以下の場合は彼女にフィードバックを送り，改善を促してください．
"""
            ),
            MessagesPlaceholder(variable_name="conv")
        ])
        self.manager_model = manager_prompt | gemini_flash.with_structured_output(ManagerFormat)
        # state graphを作成
        workflow = StateGraph(MessagesState)
        workflow.add_node("talk", self.call_talk_model)
        workflow.add_node("assist", self.call_assist_model)
        workflow.add_node('manager', self.call_manager_model)
        workflow.add_node("fix_format", self.fix_format)
        workflow.add_conditional_edges("talk", self.talk_cond_func)
        workflow.add_conditional_edges("manager", self.manager_cond_func)
        workflow.add_edge(START, "talk")
        workflow.add_edge("assist", "talk")
        workflow.add_edge("fix_format", "talk")
        self.graph = workflow.compile()
        self.youtube.start_monitoring(url)
    def add_history(self, message: BaseMessage):
        if len(self.message_history) >= self.mh_limit:
            self.message_history.pop(0)
        self.message_history.append(message)
    def get_history(self, length: int = 4) -> str:
        msgs = self.message_history[-length:]
        return "\n".join([msg.content for msg in msgs])
    def create_vector_retriever(self, top_k: int = 5, path: str = "./chroma-db"):
        embeddings = HuggingFaceEmbeddings(model_name="sbintuitions/sarashina-embedding-v1-1b")
        client = chromadb.PersistentClient(path=path)
        vector_store = Chroma(
            collection_name="ai-tuber",
            embedding_function=embeddings,
            client=client
        )
        vector_retriever = vector_store.as_retriever(search_kwargs={"k": top_k})
        return vector_retriever
    def add_data_to_vr(self, vector_retriever, texts , metadata=None):
        if not texts:
            return
        if not isinstance(texts, list):
            texts = [texts]
        vs = vector_retriever.vectorstore
        ids = [f"doc_{i}" for i in range(len(texts))]
        vs.add_texts(texts=texts, ids=ids, metadatas=metadata if metadata else [{}]*len(texts))
    def talk_cond_func(self, state: MessagesState) -> Literal["assist", "manager"]:
        last_message = state['messages'][-1].content
        last_message = TalkFormat.model_validate_json(last_message)
        if last_message.action == "Think" or last_message.action == "WebSearch":
            return "assist"
        return "manager"
    def manager_cond_func(self, state: MessagesState) -> Literal["fix_format", END]:
        last_message = state['messages'][-1].content
        last_message = ManagerFormat.model_validate_json(last_message)
        if last_message.score > 2:
            return END
        return "fix_format"
    def call_talk_model(self, state: MessagesState):
        last_msg = state['messages'][-1].content
        input = TalkInput.model_validate_json(last_msg)
        input.input = input.input.replace("\n", "")
        setting_docs = self.setting_vr.invoke(input.input)
        memory_docs = self.memory_vr.invoke(input.input)
        setting = "\n".join([doc.page_content for doc in setting_docs])
        memory = "\n".join([doc.page_content for doc in memory_docs])
        history = self.message_history
        if not history:
            history = [HumanMessage(content="No conversation history")]
        message = [HumanMessage(content=f"setting: <{setting}>\nmemory: <{memory}>\nname: {input.name}\ninput: {input.input}")]
        input_message = {"message": message, "history": history}
        response = self.talk_model.invoke(input_message)
        self.add_history(HumanMessage(content=f"{input.name}: {input.input}"))
        self.add_history(AIMessage(content=f"雲霧星奈: {response.reply}"))
        self.server.send_message_to_all(response.reply, response.action, response.emotion)
        save_data = f"{input.name}: {input.input} 雲霧星奈: {response.reply}\n"
        print(save_data)
        self.add_data_to_vr(self.memory_vr, [save_data])
        with open("./memory.txt", "a", encoding="utf-8") as f:
            f.write(save_data)
        response = response.model_dump_json()
        return {"messages": [response]}
    async def call_assist_model(self, state: MessagesState):
        conversation = self.get_history()
        last_message = state['messages'][-1].content
        last_message = TalkFormat.model_validate_json(last_message)
        input = {"input": [HumanMessage(content=f"tool: {last_message.action}\nconversation: {conversation}")]}
        response = await self.assist_model.ainvoke(input)
        talk_input = TalkInput(name=last_message.action, input=response["output"]).model_dump_json()
        return {"messages": [talk_input]}
    def call_manager_model(self, state: MessagesState):
        conversation = self.get_history()
        input = {'conv': [HumanMessage(content=conversation)]}
        response = self.manager_model.invoke(input)
        response = response.model_dump_json()
        return {"messages": [response]}
    def fix_format(self, state: MessagesState):
        last_message = state['messages'][-1].content
        last_message = ManagerFormat.model_validate_json(last_message)
        self.youtube.send_chat_message(f"マネージャー: {last_message.feedback}")
        print(f"マネージャー: {last_message.feedback}")
        msg = TalkInput(name="manager", input=last_message.feedback).model_dump_json()
        return {"messages": [msg]}
    def main(self):
        comment = self.youtube.get_random_comment()
        name, input = comment['author'], comment['text']
        if name and input:
            self.server.unity_flag = False
            self.server.send_message_to_all(reply=input, action="Message", emotion=name)
            print(f"取得したコメント: {name}: {input}")
            agent_input = TalkInput(name=name, input=input).model_dump_json()
            asyncio.run(self.graph.ainvoke({"messages": [agent_input]}))
            # self.server.unity_flagがTrueになったら関数を抜ける
            while not self.server.unity_flag:
                time.sleep(1)
                pass

if __name__ == "__main__":
    # YouTubeのライブ配信URL
    video_url = "https://www.youtube.com/watch?v=4xRbzyHDTrA"
    # AItuberを開始
    aituber = AItuber(
        url=video_url,
        port=5000
    )
    try:
        while True:
            aituber.main()
    except KeyboardInterrupt:
        print("\n終了します")