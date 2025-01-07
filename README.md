# AITuber
### アーキテクチャ
https://app.diagrams.net/#G1iLug5D_uOQoOh8EOPjuQBjL6lOTSvr2I#%7B%22pageId%22%3A%22Wsucz42x5W8DNMzrabuT%22%7D

### 全体の流れ
あるコードを実行すると，Unityのアプリとブラウザが実行され，その画面をキャプチャしてYoutubeに配信を始める．
前回の応答として入力されたコメント以降のコメントをランダムに抽選する。
Talk ModelはコメントとRAGの結果を入力としてテキストを出力する．
Talk Modelに対する入出力をAssist Modelに入力して，アクションを決定する（指摘，なにもしない，Web，思考）
それと同時にテキストを音声に変換して，変換終了後に，文字と音声を同時に表示する．
Assist Modelのアクションによってキャラクターの動作が変化する．何もしない，を選択した場合は次のコメントを受け取る．
指摘，を選択した場合は，Talk Modelに話しかける．
Web検索，を選択した場合はWeb Modelが動いてブラウジングをする．その結果をTalk Model（もしくは間にAssist Modelを入れる）に伝える
思考，を選択した場合はThinking Modelが動いて思考する．その結果をTalk Model（もしくは間にAssist Modelを入れる）に伝える
以上の動作を繰り返す．

### 必要な技術
- モデルのプロンプトや対話を評価
- Youtubeコメント取得
- PythonとUnity間の通信（動作コマンドとか，テキストとか）
- UnityでAvisSpeechを使う
- Unityキャラモーション(音声のピッチや大きさに応じて体を揺らす（縦・横）)
- Unityリップシンク
- Youtube配信の実行
- キャラ設定を作りこむ
- ブラウザを特定の領域に開く方法
- Unityのexe化
- PythonからUnity起動
- PythonからOBS APIで配信
- PythonからStream APIで配信作成
- browser-useでブラウザ画面が閉じないようにする．出来たら，既に開いているブラウザを指定できるようにする．
- browser-useのdeepseek対応 https://hamaruki.com/deepseek-v3-browser-use-webui/

### LLM
- Talk Model
FT済みのGPT-4oを使う．
Talk Modelはプロンプトにより，Assist Modelの指摘は素直に受け取るようになっている．
また，プロンプトで思考が必要な場合は，それをほのめかすような発言を行うように設定されている（もう少し考えてみる，など）
知識が必要な場合は，それをほのめかすような発言を行う（ちょっと調べてみるね，など）
RAGでキャラ設定や会話履歴を与えられる．
感情を出力

- Assist Model
Gemini 2.0 flash
Talk Modelの入力と発言が与えられ，それに対して指摘を行う．
もしくは，検索や深い思考が必要と判断した場合は，Web ModelやThinking Modelに指示を与える
RAGでTalk Modelのキャラ設定を与えられている．
- Web Model
gpt-4o-mini
Assist Modelの指示によりWebブラウジングをして，その結果を報告する
- Thinking Model
Gemini Thinking
Assist Modelの指示により，より深い思考を行い，その結果を報告する

### setup
```
conda create -n ai_tuber python=3.12
conda activate ai_tuber
pip install langchain
pip install langchain_openai
pip install langchain_google_genai
pip install langgraph
pip install google-generativeai
pip install python-dotenv
pip install browser-use
playwright install
pip install langchain_community
winget install Microsoft.VisualStudio.2022.BuildTools
pip install chromadb
pip install langchain_chroma
pip install sentence-transformers
pip install sentencepiece
pip install langchain_huggingface
```
`.env`ファイルを作成し，ルートに配置

### Youtube関連
https://qiita.com/Tomonobu3110/items/24c4e256498e1c4de922