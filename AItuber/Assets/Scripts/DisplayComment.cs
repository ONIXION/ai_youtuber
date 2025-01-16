using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;

public class DisplayComment : MonoBehaviour
{
    [SerializeField]
    private TextMeshProUGUI commentText;
    [SerializeField]
    private float updateInterval = 5.0f;
    [SerializeField]
    private int maxLines = 21;

    private void Start(){
        // デバッグのためにqueueにメッセージを追加
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        // GlobalVariables.CommentQueue.Add(new ReceiveMessageFormat { reply = "こんにちは吾輩は猫である．名前はまだない．", action = "", emotion = "happy" });
        StartCoroutine(DisplayCommentCoroutine());
    }

    private IEnumerator DisplayCommentCoroutine()
    {
        while (true)
        {
            int len = GlobalVariables.CommentQueue.Count;
            if (len > 0)
            {
                float delta = updateInterval / len;
                var comment = GlobalVariables.CommentQueue[0];
                // 新しいコメントを作成
                string newComment = comment.emotion + " : " + comment.reply;
                // 現在のテキストを保持
                string currentText = commentText.text;
                // 新しいコメントを一時的に追加して行数をチェック
                string tempText = string.IsNullOrEmpty(currentText) ? newComment : currentText + "\n" + newComment;
                commentText.text = tempText;
                // 実際の表示行数が最大行数を超えている場合、古い行を削除
                if (commentText.textInfo.lineCount > maxLines)
                {
                    // 現在のテキストから最初の行を削除
                    int firstLineBreak = currentText.IndexOf('\n');
                    if (firstLineBreak == -1)
                    {
                        currentText = "";
                    }
                    else
                    {
                        currentText = currentText.Substring(firstLineBreak + 1);
                    }
                    tempText = string.IsNullOrEmpty(currentText) ? newComment : currentText + "\n" + newComment;
                    commentText.text = tempText;
                }
                GlobalVariables.CommentQueue.RemoveAt(0);
                yield return new WaitForSeconds(delta);
            }
            else
            {
                yield return null;
            }
        }
    }
}
