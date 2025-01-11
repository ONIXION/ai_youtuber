# AI Vtuber: AIエージェントによるYoutube配信システム
![image2](image_data\capture.png?raw=true)
## アーキテクチャ
![image1](image_data\AItuberフロー.drawio.png?raw=true)

1. YouTubeDataAPIを利用してYouTubeからコメントを取得する
2. コメントをUnityに送信して表示する
3. ランダムにコメントを抽選してUnityに送る
4. コメントを棒読みちゃんで読み上げる
5. Talk ModelがコメントとRAGを入力としてテキストを出力する
6. テキストをUnityに送り，AivisSpeechで音声に変換する
7. Talk Modelがアクションを指定した場合，Assist Model（=Agent）を呼び出してタスクを実行する
8. Talk Modelが出力したアクションや感情によってUnityのキャラクターの振舞いが変化する

## エージェントシステム
- Talk Model\
RAGでキャラ設定や会話履歴を与えられる．\
通常の返答に加えて，感情や行動を出力する．

- Assist Model\
Talk Modelの出力の行動がNothingではなかった場合に呼び出される．\
browser-useとThinking Modelをツールとして与えられたエージェントとなっており，Talk Modelが指定した行動に応じて，文脈を読んでタスクを実行する．
- BrowserUse\
Assist Modelの指示によりWebブラウジングをして，その結果を報告する
- Thinking Model\
Assist Modelの指示により，より深い思考を行い，その結果を報告する

## セットアップ
- リポジトリのダウンロード
```
git clone https://github.com/ONIXION/ai_youtuber.git -b delete_manager
cd ai_youtuber
```
- Python環境の構築
```
conda create -n ai_tuber python=3.12
conda activate ai_tuber
pip install -r requirements.txt
```
- 環境変数の準備\
`.env`ファイルを作成し，ルート（`ai_youtuber/`）に配置\
中に環境変数を書き込む．（適宜追加すること）
```
OPENAI_API_KEY='sk-xxxxxxxxxxxxxxxxxxxxxxxxx'
GOOGLE_API_KEY='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
```
- client_secrets.json\
[ここらへん](https://qiita.com/Tomonobu3110/items/24c4e256498e1c4de922)のサイトを参考にしてYouTubeDataAPIv3を使えるようにする．\
途中で認証情報をダウンロードする所があるので，そこでダウンロードしたjsonファイルを`client_secrets.json`と名前を変更してルートに配置する．
- AivisSpeechのインストール\
[こちら](https://aivis-project.com/#products-aivisspeech)からダウンロードしてインストール．
- 棒読みちゃんのインストール\
[こちら](https://chi.usamimi.info/Program/Application/BouyomiChan/)からダウンロードしてインストール.
- OBS Studioをインストール\
[こちら](https://obsproject.com/ja/download)からOBS Studioをインストール.\
OBSとYoutubeを連携させておく（説明は省略）．
- Unityのセットアップ\
Unityバージョンは2022.3.42f1を使う．\
Unity HubからAdd project from diskでプロジェクトを追加できるはず．\
そのままプロジェクトが動作するかは未検証．\
フォントのサイズが大きくてgitに載らなかったので，[こちら](https://drive.google.com/file/d/1xRp-VVSHNd86f_sLbh7pi-z4gnk9Ft3T/view?usp=sharing)からダウンロードして`AItuber\Assets\Fonts\NotoSansJP-Medium SDF.asset`に配置する．\
ビルドしてAItuber.exeを作成しておく事．
- main.pyの35行目前後にchrome.exeのパスを指定する箇所があるので変更する

### 動かし方
- main.pyを実行する
- AivisSpeechとBouyomiChanを起動する
- AItuver.exeを実行する
- Youtubeで配信を開始する\
配信したことがない場合，配信できるようになるまで１日かかる\
画面右上の`+作成`から`ライブ配信を開始`を選択．

![image3](image_data\livestream_setup.png?raw=true)

- OBSでウィンドウの設定をする\
自動的にChromeが立ち上がるので，その画面をウィンドウキャプチャする.\
その後，AItuver.exeの画面を`ウィンドウキャプチャ`>`AItuber`>`キャプチャ方法：Windows10`でキャプチャする．
また，`カーソルをキャプチャする`のチェックを外しておくと良い．
- クロマキーを設定する\
AItuber.exeのウィンドウキャプチャを右クリック>フィルタ>エフェクトフィルタ>クロマキーを追加する.
- ウィンドウ配置を調整する\
Chromeの画面がAItuber.exeのクロマキーで抜いた部分に来るように配置する．\
この時，Chromeのレイヤが最背面に来るようにする．
- OBSの配信開始ボタンを押す
- Youtubeの配信画面から動画のURLを取得して，ポップアップウィンドウに入力する\
このURLはYoutubeStudioに表示されるものではなく，Youtubeの一般の配信画面のURLである必要がある．