﻿﻿﻿// https://github.com/TORISOUP/UnityBoyomichanClient
// USE: https://chi.usamimi.info/Program/Application/BouyomiChan/
using System;
using System.Threading;
using Cysharp.Threading.Tasks;
using UnityEngine;
using UnityBoyomichanClient;

public class BooyomiMessage : MonoBehaviour
{
    private CancellationTokenSource _cancellationTokenSource;
    private IBoyomichanClient _boyomichanClient;
    private const string DEFAULT_HOST = "127.0.0.1";
    private const int DEFAULT_PORT = 50001;
    [SerializeField]
    private int DEFAULT_SPEED = 100; // 50~200
    [SerializeField]
    private int DEFAULT_PITCH = 120; // 60~190
    [SerializeField]
    private int DEFAULT_VOLUME = 100; // 0~100
    [SerializeField]
    private VoiceType DEFAULT_VOICE_TYPE = VoiceType.Male1; // 棒読みちゃん画面上の設定を使用

    private void Start()
    {
        // デバッグ用にqueueにメッセージを追加
        // GlobalVariables.MessageQueue.Add(new ReceiveMessageFormat { reply = "こんにちは", action = "", emotion = "" });
        GlobalVariables.BooyomiState = 0;
        _cancellationTokenSource = new CancellationTokenSource();
        // TCP接続を確立
        _boyomichanClient = new TcpBoyomichanClient(DEFAULT_HOST, DEFAULT_PORT);
        // メッセージキューの監視を開始
        CheckMessageQueue(_cancellationTokenSource.Token).Forget();
        // タスク数の監視を開始
        CheckTaskCount(_cancellationTokenSource.Token).Forget();
    }

    private async UniTask CheckMessageQueue(CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            if (_boyomichanClient != null && GlobalVariables.MessageQueue.Count > 0 && GlobalVariables.AivisState != 2)
            {
                GlobalVariables.BooyomiState = 1; // 音声合成中
                var message = GlobalVariables.MessageQueue[0];
                if (!string.IsNullOrEmpty(message.reply))
                {
                    GlobalVariables.BooyomiState = 0;
                    await _boyomichanClient.TalkAsync(
                        message.reply,
                        DEFAULT_SPEED,
                        DEFAULT_PITCH,
                        DEFAULT_VOLUME,
                        DEFAULT_VOICE_TYPE,
                        token
                    );
                }
                // メッセージを送信したら削除
                GlobalVariables.MessageQueue.RemoveAt(0);
            }

            await UniTask.Delay(TimeSpan.FromMilliseconds(100), cancellationToken: token);
        }
    }

    private async UniTask CheckTaskCount(CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            if (_boyomichanClient != null)
            {
                // 残りのタスク数取得
                var count = await _boyomichanClient.GetTaskCountAsync(token);
                if (GlobalVariables.BooyomiState == 1 && count > 0)
                {
                    GlobalVariables.BooyomiState = 2; // 音声出力中
                }
                if (GlobalVariables.BooyomiState == 2 && count == 0)
                {
                    GlobalVariables.BooyomiState = 0; // 停止
                    Debug.Log("読み上げタスクが完了しました");
                }
                // Debug.Log(GlobalVariables.BooyomiState);
            }

            await UniTask.Delay(TimeSpan.FromMilliseconds(100), cancellationToken: token);
        }
    }

    private void OnDestroy()
    {
        _boyomichanClient?.Dispose();
        _boyomichanClient = null;
        _cancellationTokenSource.Cancel();
        _cancellationTokenSource.Dispose();
    }
}
