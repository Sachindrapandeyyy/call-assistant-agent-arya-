package com.sachindra.callassistant

import android.content.Context
import android.content.SharedPreferences
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.widget.SwitchCompat
import androidx.fragment.app.Fragment
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class AssistantFragment : Fragment() {

    private lateinit var prefs: SharedPreferences
    private lateinit var switchAutoAnswer: SwitchCompat
    private lateinit var etDelay: EditText
    private lateinit var btnSaveDelay: Button
    private lateinit var etHost: EditText
    private lateinit var etPort: EditText
    private lateinit var btnConnectWs: Button
    private lateinit var tvWsStatus: TextView

    private lateinit var etChatQuery: EditText
    private lateinit var btnSendChat: Button
    private lateinit var layoutChatReply: LinearLayout
    private lateinit var tvChatReply: TextView

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        val view = inflater.inflate(R.layout.fragment_assistant, container, false)
        val context = requireContext()
        prefs = context.getSharedPreferences(MainActivity.PREFS_NAME, Context.MODE_PRIVATE)

        switchAutoAnswer = view.findViewById(R.id.switchAutoAnswer)
        etDelay = view.findViewById(R.id.etDelay)
        btnSaveDelay = view.findViewById(R.id.btnSaveDelay)
        etHost = view.findViewById(R.id.etHost)
        etPort = view.findViewById(R.id.etPort)
        btnConnectWs = view.findViewById(R.id.btnConnectWs)
        tvWsStatus = view.findViewById(R.id.tvWsStatus)

        etChatQuery = view.findViewById(R.id.etChatQuery)
        btnSendChat = view.findViewById(R.id.btnSendChat)
        layoutChatReply = view.findViewById(R.id.layoutChatReply)
        tvChatReply = view.findViewById(R.id.tvChatReply)

        switchAutoAnswer.isChecked = prefs.getBoolean(MainActivity.KEY_AUTO_ANSWER, true)
        etDelay.setText(prefs.getInt(MainActivity.KEY_DELAY_MS, 4000).toString())
        etHost.setText(prefs.getString(MainActivity.KEY_WS_HOST, "192.168.29.205"))
        etPort.setText(prefs.getInt(MainActivity.KEY_WS_PORT, 8000).toString())

        switchAutoAnswer.setOnCheckedChangeListener { _, isChecked ->
            prefs.edit().putBoolean(MainActivity.KEY_AUTO_ANSWER, isChecked).apply()
            Toast.makeText(context, "Auto-answer: ${if (isChecked) "ON" else "OFF"}", Toast.LENGTH_SHORT).show()
        }

        btnSaveDelay.setOnClickListener {
            val delay = etDelay.text.toString().toIntOrNull() ?: 4000
            prefs.edit().putInt(MainActivity.KEY_DELAY_MS, delay).apply()
            Toast.makeText(context, "Delay saved: ${delay}ms", Toast.LENGTH_SHORT).show()
        }

        btnConnectWs.setOnClickListener {
            val host = etHost.text.toString().trim()
            val port = etPort.text.toString().toIntOrNull() ?: 8000
            prefs.edit().putString(MainActivity.KEY_WS_HOST, host).putInt(MainActivity.KEY_WS_PORT, port).apply()

            tvWsStatus.text = "Status: ⏳ Connecting..."
            tvWsStatus.setTextColor(0xFFFFC107.toInt())

            WebSocketTelephonyClient.updateServerConfig(host, port) { connected ->
                activity?.runOnUiThread {
                    if (connected) {
                        tvWsStatus.text = "Status: ✅ CONNECTED to PC"
                        tvWsStatus.setTextColor(0xFF188038.toInt())
                        Toast.makeText(context, "Connected to Laptop AI Backend!", Toast.LENGTH_SHORT).show()
                    } else {
                        tvWsStatus.text = "Status: ❌ DISCONNECTED"
                        tvWsStatus.setTextColor(0xFFD93025.toInt())
                    }
                }
            }
        }

        btnSendChat.setOnClickListener {
            val query = etChatQuery.text.toString().trim()
            if (query.isNotEmpty()) {
                sendChatQuery(query)
            }
        }

        updateStatus()
        return view
    }

    private fun sendChatQuery(query: String) {
        val host = etHost.text.toString().trim()
        val port = etPort.text.toString().toIntOrNull() ?: 8000
        val urlStr = "http://$host:$port/api/assistant/chat"

        layoutChatReply.visibility = View.VISIBLE
        tvChatReply.text = "⏳ Aura AI is thinking..."

        thread {
            try {
                val url = URL(urlStr)
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json; utf-8")
                conn.doOutput = true
                conn.connectTimeout = 8000
                conn.readTimeout = 12000

                val jsonBody = JSONObject().apply {
                    put("query", query)
                }

                OutputStreamWriter(conn.outputStream).use { os ->
                    os.write(jsonBody.toString())
                    os.flush()
                }

                if (conn.responseCode == 200) {
                    val responseStr = conn.inputStream.bufferedReader().use { it.readText() }
                    val jsonResp = JSONObject(responseStr)
                    val reply = jsonResp.optString("reply", "No response from AI.")
                    
                    activity?.runOnUiThread {
                        tvChatReply.text = reply
                    }
                } else {
                    activity?.runOnUiThread {
                        tvChatReply.text = "Error connecting to AI Server (HTTP ${conn.responseCode})"
                    }
                }
            } catch (e: Exception) {
                activity?.runOnUiThread {
                    tvChatReply.text = "Could not connect to PC AI: ${e.message}"
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        updateStatus()
    }

    private fun updateStatus() {
        if (WebSocketTelephonyClient.isConnected) {
            tvWsStatus.text = "Status: ✅ CONNECTED to PC"
            tvWsStatus.setTextColor(0xFF188038.toInt())
        } else {
            tvWsStatus.text = "Status: ❌ DISCONNECTED"
            tvWsStatus.setTextColor(0xFFD93025.toInt())
        }
    }
}
