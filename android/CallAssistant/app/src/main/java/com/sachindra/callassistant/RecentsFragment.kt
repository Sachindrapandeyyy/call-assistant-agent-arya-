package com.sachindra.callassistant

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.CallLog
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class RecentsFragment : Fragment() {

    private lateinit var rvRecents: RecyclerView
    private lateinit var adapter: CallLogAdapter

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        val view = inflater.inflate(R.layout.fragment_recents, container, false)
        rvRecents = view.findViewById(R.id.rvRecents)

        rvRecents.layoutManager = LinearLayoutManager(requireContext())
        adapter = CallLogAdapter(emptyList()) { number ->
            dialNumber(number)
        }
        rvRecents.adapter = adapter

        loadCallLogs()
        return view
    }

    override fun onResume() {
        super.onResume()
        loadCallLogs()
    }

    private fun loadCallLogs() {
        val context = context ?: return
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CALL_LOG) != PackageManager.PERMISSION_GRANTED) {
            return
        }

        val logs = mutableListOf<CallLogModel>()
        try {
            val cursor = context.contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                arrayOf(
                    CallLog.Calls._ID,
                    CallLog.Calls.CACHED_NAME,
                    CallLog.Calls.NUMBER,
                    CallLog.Calls.TYPE,
                    CallLog.Calls.DATE,
                    CallLog.Calls.DURATION
                ),
                null,
                null,
                "${CallLog.Calls.DATE} DESC"
            )

            cursor?.use {
                val idIdx = it.getColumnIndex(CallLog.Calls._ID)
                val nameIdx = it.getColumnIndex(CallLog.Calls.CACHED_NAME)
                val numIdx = it.getColumnIndex(CallLog.Calls.NUMBER)
                val typeIdx = it.getColumnIndex(CallLog.Calls.TYPE)
                val dateIdx = it.getColumnIndex(CallLog.Calls.DATE)
                val durIdx = it.getColumnIndex(CallLog.Calls.DURATION)

                while (it.moveToNext()) {
                    val id = if (idIdx != -1) it.getString(idIdx) else ""
                    val name = if (nameIdx != -1) it.getString(nameIdx) else null
                    val number = if (numIdx != -1) it.getString(numIdx) else "Unknown"
                    val type = if (typeIdx != -1) it.getInt(typeIdx) else CallLog.Calls.INCOMING_TYPE
                    val date = if (dateIdx != -1) it.getLong(dateIdx) else 0L
                    val duration = if (durIdx != -1) it.getLong(durIdx) else 0L

                    logs.add(CallLogModel(id, name, number, type, date, duration))
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }

        adapter.updateData(logs)
        fetchAiSummaries(logs)
    }

    private fun fetchAiSummaries(logs: List<CallLogModel>) {
        val context = context ?: return
        val prefs = context.getSharedPreferences(MainActivity.PREFS_NAME, Context.MODE_PRIVATE)
        val host = prefs.getString(MainActivity.KEY_WS_HOST, "192.168.29.205")
        val port = prefs.getInt(MainActivity.KEY_WS_PORT, 8000)

        thread {
            try {
                val url = URL("http://$host:$port/api/calls")
                val conn = url.openConnection() as HttpURLConnection
                conn.connectTimeout = 3000
                conn.readTimeout = 4000
                if (conn.responseCode == 200) {
                    val resp = conn.inputStream.bufferedReader().use { it.readText() }
                    val arr = JSONArray(resp)
                    val map = mutableMapOf<String, String>()
                    for (i in 0 until arr.length()) {
                        val obj = arr.getJSONObject(i)
                        val num = obj.optString("caller_number", "").replace(" ", "").replace("-", "")
                        val sum = obj.optString("summary", "")
                        if (num.isNotEmpty() && sum.isNotEmpty() && sum != "null") {
                            map[num] = sum
                        }
                    }
                    activity?.runOnUiThread {
                        adapter.updateData(logs, map)
                    }
                }
            } catch (e: Exception) {
                // Ignore if offline
            }
        }
    }

    private fun dialNumber(number: String) {
        PhoneUtils.placeOutgoingCall(requireContext(), number)
    }
}
