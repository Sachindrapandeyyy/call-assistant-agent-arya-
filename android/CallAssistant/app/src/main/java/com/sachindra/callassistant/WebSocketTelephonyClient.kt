package com.sachindra.callassistant

import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

object WebSocketTelephonyClient {
    private const val TAG = "[TELEPHONY_WS]"
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private val executor = Executors.newSingleThreadExecutor()
    private var serverUrl: String = "ws://192.168.29.205:8000/ws/telephony"
    var isConnected = false
    var onConnectionStateChanged: ((Boolean) -> Unit)? = null

    fun updateServerConfig(ip: String, port: Int, onResult: ((Boolean) -> Unit)? = null) {
        serverUrl = "ws://$ip:$port/ws/telephony"
        onConnectionStateChanged = onResult
        executor.execute {
            disconnect()
            connect()
        }
    }

    fun connect() {
        if (isConnected) {
            onConnectionStateChanged?.invoke(true)
            return
        }
        try {
            Log.d(TAG, "Connecting to backend at $serverUrl")
            val request = Request.Builder().url(serverUrl).build()
            webSocket = client.newWebSocket(request, object : WebSocketListener() {
                override fun onOpen(ws: WebSocket, response: Response) {
                    isConnected = true
                    Log.d(TAG, "Connected to backend WebSocket successfully.")
                    onConnectionStateChanged?.invoke(true)
                    sendEvent("client_connected", mapOf("device" to "Infinix Zero 5G 2023", "os" to "Android 13"))
                }

                override fun onMessage(ws: WebSocket, text: String) {
                    Log.d(TAG, "Received message from backend: $text")
                    try {
                        val json = JSONObject(text)
                        val event = json.optString("event", "")
                        if (event == "hangup_call" || event == "end_call") {
                            Log.d(TAG, "[TELEPHONY] Received auto-hangup command from Arya AI!")
                            CallAssistantInCallService.currentActiveCall?.disconnect()
                        }
                    } catch (e: Exception) {
                        Log.e(TAG, "Error handling WS message: ${e.message}")
                    }
                }

                override fun onClosing(ws: WebSocket, code: Int, reason: String) {
                    isConnected = false
                    onConnectionStateChanged?.invoke(false)
                    Log.d(TAG, "Closing WebSocket: $reason")
                }

                override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                    isConnected = false
                    onConnectionStateChanged?.invoke(false)
                    Log.d(TAG, "WebSocket Closed.")
                }

                override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                    isConnected = false
                    onConnectionStateChanged?.invoke(false)
                    Log.w(TAG, "WebSocket connection failed: ${t.message}")
                }
            })
        } catch (e: Exception) {
            Log.e(TAG, "Error initiating WebSocket: ${e.message}")
            onConnectionStateChanged?.invoke(false)
        }
    }

    fun disconnect() {
        try {
            webSocket?.close(1000, "App closed")
            webSocket = null
            isConnected = false
        } catch (e: Exception) {
            Log.e(TAG, "Error closing WebSocket: ${e.message}")
        }
    }

    fun sendEvent(eventType: String, data: Map<String, Any> = emptyMap()) {
        executor.execute {
            try {
                val json = JSONObject()
                json.put("event", eventType)
                json.put("timestamp", System.currentTimeMillis() / 1000.0)
                val dataJson = JSONObject()
                data.forEach { (key, value) -> dataJson.put(key, value) }
                json.put("data", dataJson)

                val payload = json.toString()
                Log.d(TAG, "Sending Telephony Event -> $payload")

                if (isConnected && webSocket != null) {
                    webSocket?.send(payload)
                } else {
                    Log.d(TAG, "WebSocket not connected. Attempting reconnect...")
                    connect()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send telephony event: ${e.message}")
            }
        }
    }
}
