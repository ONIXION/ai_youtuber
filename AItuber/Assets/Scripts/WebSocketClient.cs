using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using System.Net.WebSockets;

[Serializable]
public class SendTextFormat
{
    public string message;
}

public class WebSocketClient : MonoBehaviour
{
    private ClientWebSocket webSocket;
    private bool isConnecting = false;
    private bool isConnected = false;
    private bool isQuitting = false;
    private int old_aivis_state = 0;

    async void Start()
    {
        await ConnectToServer();
        if (isConnected)
        {
            await SendText("Hello from Unity!");
        }
    }

    async void Update()
    {
        if (GlobalVariables.AivisState == 2 && old_aivis_state == 1)
        {
            old_aivis_state = GlobalVariables.AivisState;
            await SendText("Finish");
        }else{
            old_aivis_state = GlobalVariables.AivisState;
        }
    }

    private async Task ConnectToServer()
    {
        if (isConnecting) return;
        isConnecting = true;
        webSocket = new ClientWebSocket();
        Uri serverUri = new Uri("ws://localhost:5000");
        try
        {
            await webSocket.ConnectAsync(serverUri, CancellationToken.None);
            Debug.Log("Connected to server");
            isConnected = true;
            StartReceiving();
        }
        catch (Exception e)
        {
            Debug.LogError($"WebSocket connection error: {e.Message}");
            Cleanup();
            await Task.Delay(5000); // Wait before retrying
            await ConnectToServer(); // Retry connection
        }
        finally
        {
            isConnecting = false;
        }
    }

    private void Cleanup()
    {
        if (webSocket != null)
        {
            try
            {
                if (webSocket.State == WebSocketState.Open)
                {
                    webSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closing", CancellationToken.None).Wait();
                }
                webSocket.Dispose();
            }
            catch (Exception e)
            {
                Debug.LogError($"Error during cleanup: {e.Message}");
            }
            webSocket = null;
        }
        isConnected = false;
    }

    private async Task SendText(string message)
    {
        if (webSocket == null || webSocket.State != WebSocketState.Open)
        {
            Debug.LogWarning("Cannot send message - WebSocket is not connected");
            return;
        }
        {
            var messageObj = new SendTextFormat { message = message };
            string jsonMessage = JsonUtility.ToJson(messageObj);
            byte[] buffer = Encoding.UTF8.GetBytes(jsonMessage);
            await webSocket.SendAsync(new ArraySegment<byte>(buffer), WebSocketMessageType.Text, true, CancellationToken.None);
            Debug.Log($"Message sent: {jsonMessage}");
        }
    }

    private async void StartReceiving()
    {
        if (webSocket == null || webSocket.State != WebSocketState.Open)
        {
            Debug.LogWarning("Cannot start receiving - WebSocket is not connected");
            return;
        }

        byte[] buffer = new byte[4096]; // Increased buffer size
        while (webSocket != null && webSocket.State == WebSocketState.Open)
        {
            try
            {
                WebSocketReceiveResult result = await webSocket.ReceiveAsync(
                    new ArraySegment<byte>(buffer),
                    CancellationToken.None);

                if (result.MessageType == WebSocketMessageType.Close)
                {
                    Debug.Log("Server requested connection close");
                    await webSocket.CloseAsync(
                        WebSocketCloseStatus.NormalClosure,
                        "Closing",
                        CancellationToken.None);
                    break;
                }

                string jsonMessage = Encoding.UTF8.GetString(buffer, 0, result.Count);
                try
                {
                    var messageObj = JsonUtility.FromJson<ReceiveMessageFormat>(jsonMessage);
                    if (messageObj != null && !string.IsNullOrEmpty(messageObj.reply))
                    {
                        Debug.Log($"Message received: {messageObj.reply}");
                        if (messageObj.action == "Comment")
                        {
                            GlobalVariables.CommentQueue.Add(messageObj);
                        }
                        else if (messageObj.action == "Message")
                        {
                            GlobalVariables.MessageQueue.Add(messageObj);
                        }
                        else
                        {
                            GlobalVariables.AgentQueue.Add(messageObj);
                        }
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"Error parsing JSON message: {e.Message}");
                }
            }
            catch (WebSocketException e)
            {
                Debug.LogError($"WebSocket error: {e.Message}");
                await HandleDisconnection();
                break;
            }
            catch (Exception e)
            {
                Debug.LogError($"Error receiving message: {e.Message}");
                await HandleDisconnection();
                break;
            }
        }
    }

    private async Task HandleDisconnection()
    {
        Cleanup();
        if (!isQuitting)
        {
            Debug.Log("Attempting to reconnect...");
            await Task.Delay(3000); // Wait before reconnecting
            await ConnectToServer();
        }
        else
        {
            Debug.Log("Application is quitting - skipping reconnection");
        }
    }

    private void OnApplicationQuit()
    {
        Debug.Log("Application quitting - cleaning up WebSocket connection");
        isQuitting = true;
        Cleanup();
    }
}
