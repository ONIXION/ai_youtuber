using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using Cysharp.Threading.Tasks;
using System.Text;
using System;

// LipSyncを実装
// https://github.com/hecomi/uLipSync

public class AivisSpeech : MonoBehaviour
{
    [SerializeField]
    private AudioSource audioSource;
    [SerializeField]
    private SkinnedMeshRenderer faceMR;
    [SerializeField]
    private Animator animator;
    private const string HOST = "localhost";
    private const int PORT = 10101;
    private const int NORMAL_SPEAKER = 888753760;
    private const int DEFAULT_SPEAKER = 888753761;
    private const int HIGH_TENSION = 888753762;
    private const int CALM = 888753763;
    private const int HAPPY = 888753764;
    private const int ANGRY_SAD = 888753765;

    private void Start()
    {
        // デバッグ用にqueueにメッセージを追加
        GlobalVariables.AgentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは", action = "", emotion = "happy" });
        GlobalVariables.AivisState = 0;
    }

    private void Update()
    {
        // AgentQueueにメッセージがある場合
        if (GlobalVariables.AgentQueue.Count > 0 && GlobalVariables.AivisState == 0)
        {
            // キューからメッセージを取り出す
            var message = GlobalVariables.AgentQueue[0];
            GlobalVariables.AgentQueue.RemoveAt(0);
            if (message.action == "Think"){
                animator.SetBool("isThinking", true);
            }
            if (message.action == "WebSearch"){
                animator.SetBool("isSearching", true);
            }
            if (message.action == "Nothing"){
                animator.SetBool("isThinking", false);
                animator.SetBool("isSearching", false);
            }
            // 音声合成を実行
            Text2VoiceAsync(message.reply, message.emotion).Forget();
        }
    }

    private async UniTask Text2VoiceAsync(string text, string emotion)
    {
        int speaker = DEFAULT_SPEAKER;
        GlobalVariables.AivisState = 1; // 音声合成中
        // emotion ["normal", "happy", "angry", "sad", "surprised", "shy", "excited", "smug", "calm"]
        if (emotion == "normal")
        {
            speaker = NORMAL_SPEAKER;
        }
        else if (emotion == "happy" || emotion == "smug")
        {
            speaker = HAPPY;
        }
        else if (emotion == "angry" || emotion == "sad")
        {
            speaker = ANGRY_SAD;
        }
        else if (emotion == "excited" || emotion == "surprised")
        {
            speaker = HIGH_TENSION;
        }
        else if (emotion == "calm")
        {
            speaker = CALM;
        }

        // emotionに応じてモーフを設定
        switch (emotion)
        {
            case "normal": // Normal
                animator.SetInteger("EmotionIdx", (int)Emotion.normal);
                break;
            case "happy": // Normal
                animator.SetInteger("EmotionIdx", (int)Emotion.happy);
                faceMR.SetBlendShapeWeight((int)Morph.warai, 100f);
                faceMR.SetBlendShapeWeight((int)Morph.nikori, 100f);
                break;
            case "angry": // ArmsCrossedPauting
                animator.SetInteger("EmotionIdx", (int)Emotion.angry);
                faceMR.SetBlendShapeWeight((int)Morph.okori, 100f);
                faceMR.SetBlendShapeWeight((int)Morph.niramu, 100f);
                faceMR.SetBlendShapeWeight((int)Morph.high_light_off, 100f);
                break;
            case "sad": // shy
                animator.SetInteger("EmotionIdx", (int)Emotion.sad);
                faceMR.SetBlendShapeWeight((int)Morph.komaru, 100f);
                faceMR.SetBlendShapeWeight((int)Morph.mayu_sita, 60f);
                break;
            case "surprised": // surprised
                animator.SetInteger("EmotionIdx", (int)Emotion.surprised);
                faceMR.SetBlendShapeWeight((int)Morph.bikkuri, 50f);
                faceMR.SetBlendShapeWeight((int)Morph.hitomi_small, 40f);
                break;
            case "shy": // shy
                animator.SetInteger("EmotionIdx", (int)Emotion.shy);
                faceMR.SetBlendShapeWeight((int)Morph.hohozome, 100f);
                faceMR.SetBlendShapeWeight((int)Morph.komaru, 70f);
                break;
            case "excited": // excited
                animator.SetInteger("EmotionIdx", (int)Emotion.excited);
                faceMR.SetBlendShapeWeight((int)Morph.star, 100f);
                break;
            case "smug": // ArmsCrossedCalm
                animator.SetInteger("EmotionIdx", (int)Emotion.smug);
                faceMR.SetBlendShapeWeight((int)Morph.okori, 50f);
                faceMR.SetBlendShapeWeight((int)Morph.zitome, 80f);
                break;
            case "calm": // Calm
                animator.SetInteger("EmotionIdx", (int)Emotion.calm);
                faceMR.SetBlendShapeWeight((int)Morph.nagomi, 15f);
                break;
        }

        try
        {
            // audio_queryリクエスト
            var queryUrl = $"http://{HOST}:{PORT}/audio_query?text={UnityWebRequest.EscapeURL(text)}&speaker={speaker}";
            var queryRequest = UnityWebRequest.Post(queryUrl, new WWWForm());
            await queryRequest.SendWebRequest();

            if (queryRequest.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"Audio query failed: {queryRequest.error}");
                GlobalVariables.AivisState = 0;
                return;
            }

            var queryResponse = queryRequest.downloadHandler.text;

            // synthesisリクエスト
            var synthesisUrl = $"http://{HOST}:{PORT}/synthesis?speaker={speaker}";
            var synthesisRequest = new UnityWebRequest(synthesisUrl, "POST");
            synthesisRequest.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(queryResponse));
            synthesisRequest.downloadHandler = new DownloadHandlerBuffer();
            synthesisRequest.SetRequestHeader("Content-Type", "application/json");
            synthesisRequest.SetRequestHeader("accept", "audio/wav");

            await synthesisRequest.SendWebRequest();

            if (synthesisRequest.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"Synthesis failed: {synthesisRequest.error}");
                return;
            }
            if (emotion == "surprised")
            {
                animator.SetInteger("EmotionIdx", (int)Emotion.waiting);
            }
            // GlobalVariables.BooyomiState == 0になるまで待機
            while (GlobalVariables.BooyomiState != 0)
            {
                await UniTask.Yield();
            }
            GlobalVariables.AivisState = 2; // 音声出力中
            // 音声データの取得と再生
            var audioData = synthesisRequest.downloadHandler.data;
            await PlayAudioData(audioData);
        }
        catch (Exception e)
        {
            Debug.LogError($"Error in Text2Voice: {e.Message}");
        }
        finally
        {
            // モーフを元に戻す
            faceMR.SetBlendShapeWeight((int)Morph.warai, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.nikori, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.okori, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.niramu, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.high_light_off, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.komaru, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.mayu_sita, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.bikkuri, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.hitomi_small, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.hohozome, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.star, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.zitome, 0f);
            faceMR.SetBlendShapeWeight((int)Morph.nagomi, 0f);
            animator.SetTrigger("FinishTalk");
            GlobalVariables.AivisState = 0;
        }
    }

    private async UniTask PlayAudioData(byte[] audioData)
    {
        // WAVバイトデータからAudioClipを作成
        var audioClip = WAVUtility.ToAudioClip(audioData);
        // AudioSourceコンポーネントを取得または作成
        if (audioSource == null)
        {
            audioSource = gameObject.AddComponent<AudioSource>();
        }
        // AudioClipを設定して再生
        audioSource.clip = audioClip;
        audioSource.Play();

        // 再生が完了するまで待機
        while (audioSource.isPlaying)
        {
            await UniTask.Yield();
        }
    }
}

// WAVユーティリティクラス
public static class WAVUtility
{
    public static AudioClip ToAudioClip(byte[] wavData)
    {
        // WAVヘッダーをスキップ (44バイト)
        const int headerSize = 44;
        // AudioClipを作成
        var audioClip = AudioClip.Create("voice", 
            (wavData.Length - headerSize) / 2, // 16bitなので2で割る
            1, // モノラル
            44100, // サンプリングレート
            false);

        // 音声データをfloat配列に変換
        var audioData = new float[(wavData.Length - headerSize) / 2];
        for (int i = 0; i < audioData.Length; i++)
        {
            // 16bitデータをfloatに変換 (-1.0f to 1.0f)
            short sample = BitConverter.ToInt16(wavData, headerSize + i * 2);
            audioData[i] = sample / 32768f;
        }

        audioClip.SetData(audioData, 0);
        return audioClip;
    }
}
