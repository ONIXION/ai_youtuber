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
from browser_use import Agent
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import chromadb
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.globals import set_verbose, set_debug

DEBUG = True
set_debug(DEBUG)
set_verbose(DEBUG)

class TalkInput(BaseModel):
    name: str
    input: str

# TalkModelの出力形式を定義
class TalkFormat(BaseModel):
    reply: str = Field(..., description="マネージャーや視聴者に対する返答")
    action: Literal["Nothing", "Think", "WebSearch"] = Field(..., description="次の行動．以下のいずれかから選択: Nothing, Think, WebSearch")
    emotion: Literal["normal", "happy", "angry", "sad", "surprised", "shy", "excited", "smug", "teasing", "confused"] = Field(..., description="現在の感情．以下のいずれかから選択: normal, happy, angry, sad, surprised, shy, excited, smug, teasing, confused")

class ManagerFormat(BaseModel):
    feedback: str = Field(..., description="Vtuberに対するフィードバック．scoreが2以下の場合に記述．")
    score: int = Field(..., ge=0, le=9, description="Vtuberの発言に対する評価．0から9の10段階．")

class AItuber:
    def __init__(self):
        gemini_flash = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.7)
        gemini_think = ChatGoogleGenerativeAI(model="gemini-2.0-flash-thinking-exp-1219", temperature=0.7)
        tool_list = [self.think, self.web_search]
        self.message_history = []
        self.mh_limit = 10 # 10なら対話5回分の履歴を保持
        self.session_id = "ai-tuber"
        self.get_comment_time = None # youtubeのコメント取得時間
        self.setting_vr = self.create_vector_retriever(top_k=1, path="./chroma-db-setting")
        self.memory_vr = self.create_vector_retriever(top_k=3, path="./chroma-db-memory")
        # setting.txtのデータをvector_retrieverに追加
        with open("./setting.txt", "r") as f:
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
        teasing: からかい
        confused: 混乱

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
            HumanMessage(content="tool: {tool}\nconversation: {conversation}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        self.assist_model = AgentExecutor(
            agent = create_tool_calling_agent(gemini_flash, tool_list, assist_prompt),
            tools=tool_list
        )
        # ThinkModelの設定
        think_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""
入力された内容について深く考え，適切な返答を生成してください．
返答は必ず日本語で行ってください．
また，返答が長くなりすぎないように注意してください．
"""
            ),
            MessagesPlaceholder(variable_name="messages")
        ])
        self.think_model = think_prompt | gemini_think
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
        setting_docs = self.setting_vr.invoke(input.input)
        memory_docs = self.memory_vr.invoke(input.input)
        setting = "\n".join([doc.page_content for doc in setting_docs])
        memory = "\n".join([doc.page_content for doc in memory_docs])
        history = self.message_history
        # historyが空のリストの場合は適当な文字列を入れる
        if not history:
            history = [HumanMessage(content="No conversation history")]
        message = [HumanMessage(content=f"setting: <{setting}>\nmemory: <{memory}>\nname: {input.name}\ninput: {input.input}")]
        input_message = {"message": message, "history": history}
        print("TalkModel input: ", input_message)
        response = self.talk_model.invoke(input_message)
        print("TalkModel output: ", response)
        self.add_history(HumanMessage(content=f"{input.name}: {input.input}"))
        self.add_history(AIMessage(content=f"雲霧星奈: {response.reply}"))
        self.send_unity(response)
        save_data = f"{input.name}: {input.input} 雲霧星奈: {response.reply}\n"
        self.add_data_to_vr(self.memory_vr, [save_data])
        with open("./memory.txt", "a", encoding="utf-8") as f:
            f.write(save_data)
        response = response.model_dump_json()
        return {"messages": [response]}
    def call_assist_model(self, state: MessagesState):
        conversation = self.get_history()
        last_message = state['messages'][-1].content
        last_message = TalkFormat.model_validate_json(last_message)
        input = {'tool': last_message.action, 'conversation': conversation}
        print("AssistModel input: ", input)
        response = self.assist_model.invoke(input)
        print("AssistModel output", response)
        talk_input = TalkInput(name=last_message.action, input=response).model_dump_json()
        return {"messages": [talk_input]}
    def call_manager_model(self, state: MessagesState):
        conversation = self.get_history()
        input = {'conv': [HumanMessage(content=conversation)]}
        print("ManagerModel input: ", input)
        response = self.manager_model.invoke(input)
        print("ManagerModel output", response)
        response = response.model_dump_json()
        return {"messages": [response]}
    def fix_format(self, state: MessagesState):
        last_message = state['messages'][-1].content
        last_message = ManagerFormat.model_validate_json(last_message)

        # Youtubeにコメント書き込み
        
        msg = TalkInput(name="manager", input=last_message.feedback).model_dump_json()
        return {"messages": [msg]}
        # return {"messages": [TalkInput(name="manager", input=last_message.feedback)]}
    def send_unity(self, data: TalkFormat):
        
        # http通信でUnityにデータを送信
        
        pass
    @tool
    async def think(self,
        input: Annotated[str, "what to think about"],
    ) -> str:
        """Think about the input."""
        response = await self.think_model.invoke({'messages': input})
        return response.content
    @tool
    async def web_search(self,
        input: Annotated[str, "what to search for"],
    ) -> str:
        """Search the web for the input."""
        agent = Agent(
            task=input,
            llm=ChatOpenAI(model="gpt-4o-mini"),
        )
        result = await agent.run()
        return result
    def main(self, name:str = None, input:str = None):
        if name is None or input is None:
            name, input = self.get_youtube_comment()
        input = TalkInput(name=name, input=input).model_dump_json()
        events = self.graph.stream(
            {"messages": [input]},
            # stream_mode="values"
        )
        for event in events:
            print(event)
        return
    def get_youtube_comment(self):

        # youtubeのコメントを取得
        
        name = "ユーザーA"
        input = "ホログラム宇宙論についてWebで調べて"
        return name, input

if __name__ == "__main__":
    aituber = AItuber()
    aituber.main()