package com.sachindra.callassistant

import android.provider.CallLog
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class CallLogAdapter(
    private var callLogs: List<CallLogModel>,
    private val onCallClicked: (String) -> Unit
) : RecyclerView.Adapter<CallLogAdapter.CallLogViewHolder>() {

    private val aiSummariesMap = mutableMapOf<String, String>() // number -> summary json

    private val gradientDrawables = intArrayOf(
        R.drawable.bg_galaxy_avatar_nebula,
        R.drawable.bg_galaxy_avatar_supernova,
        R.drawable.bg_galaxy_avatar_solar
    )

    fun updateData(newLogs: List<CallLogModel>, summaries: Map<String, String> = emptyMap()) {
        callLogs = newLogs
        aiSummariesMap.clear()
        aiSummariesMap.putAll(summaries)
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): CallLogViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_call_log, parent, false)
        return CallLogViewHolder(view)
    }

    override fun onBindViewHolder(holder: CallLogViewHolder, position: Int) {
        val log = callLogs[position]
        val displayName = if (!log.name.isNullOrEmpty()) log.name else log.number
        holder.tvCallerName.text = displayName

        val initial = if (!log.name.isNullOrEmpty() && log.name.first().isLetter()) log.name.first().uppercase() else "👤"
        holder.tvAvatarInitial.text = initial

        val gradIdx = Math.abs(displayName.hashCode()) % gradientDrawables.size
        holder.tvAvatarInitial.setBackgroundResource(gradientDrawables[gradIdx])
        holder.tvAvatarInitial.background?.setTintList(null)

        val sdf = SimpleDateFormat("dd MMM, hh:mm a", Locale.getDefault())
        val dateStr = sdf.format(Date(log.date))
        val durStr = if (log.duration > 0) "${log.duration}s" else ""

        when (log.type) {
            CallLog.Calls.INCOMING_TYPE -> {
                holder.tvCallDetails.text = "Incoming • $dateStr $durStr".trim()
                holder.tvCallerName.setTextColor(0xFFFFFFFF.toInt())
            }
            CallLog.Calls.OUTGOING_TYPE -> {
                holder.tvCallDetails.text = "Outgoing • $dateStr $durStr".trim()
                holder.tvCallerName.setTextColor(0xFFFFFFFF.toInt())
            }
            CallLog.Calls.MISSED_TYPE -> {
                holder.tvCallDetails.text = "Missed • $dateStr"
                holder.tvCallerName.setTextColor(0xFFFF4D6D.toInt())
            }
            else -> {
                holder.tvCallDetails.text = "$dateStr $durStr".trim()
                holder.tvCallerName.setTextColor(0xFFFFFFFF.toInt())
            }
        }

        val timeSdf = SimpleDateFormat("hh:mm a", Locale.getDefault())
        holder.tvCallTime.text = timeSdf.format(Date(log.date))

        // Check if there is an actual real AI summary from backend
        val cleanNumber = log.number.replace(" ", "").replace("-", "")
        val rawSummary = aiSummariesMap[cleanNumber] ?: aiSummariesMap[log.number]

        if (!rawSummary.isNullOrEmpty() && log.type == CallLog.Calls.INCOMING_TYPE) {
            try {
                val json = JSONObject(rawSummary)
                val reason = json.optString("reason_for_call", "")
                val msg = json.optString("message", "")
                val urgency = json.optString("urgency", "Medium")

                val displayText = if (reason.isNotEmpty() && reason != "N/A") {
                    if (msg.isNotEmpty() && msg != "N/A" && msg != reason) "$reason — \"$msg\"" else reason
                } else if (msg.isNotEmpty() && msg != "N/A") {
                    msg
                } else {
                    "Call attended by Arya AI"
                }

                holder.layoutAiSummary.visibility = View.VISIBLE
                holder.tvAiSummaryText.text = displayText

                val tvUrgency = holder.itemView.findViewById<TextView>(R.id.tvAiSummaryText)
                if (urgency.equals("Urgent", ignoreCase = true) || urgency.equals("High", ignoreCase = true)) {
                    holder.tvAiSummaryText.setTextColor(0xFFFF4D6D.toInt())
                } else {
                    holder.tvAiSummaryText.setTextColor(0xFFE0AAFF.toInt())
                }
            } catch (e: Exception) {
                holder.layoutAiSummary.visibility = View.GONE
            }
        } else {
            // Outgoing calls or regular calls without AI session have NO summary box
            holder.layoutAiSummary.visibility = View.GONE
        }

        holder.btnInfo.setOnClickListener {
            onCallClicked(log.number)
        }

        holder.itemView.setOnClickListener {
            onCallClicked(log.number)
        }
    }

    override fun getItemCount(): Int = callLogs.size

    class CallLogViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val tvAvatarInitial: TextView = view.findViewById(R.id.tvAvatarInitial)
        val tvCallerName: TextView = view.findViewById(R.id.tvCallerName)
        val tvCallDetails: TextView = view.findViewById(R.id.tvCallDetails)
        val tvCallTime: TextView = view.findViewById(R.id.tvCallTime)
        val btnInfo: ImageView = view.findViewById(R.id.btnInfo)
        val layoutAiSummary: LinearLayout = view.findViewById(R.id.layoutAiSummary)
        val tvAiSummaryText: TextView = view.findViewById(R.id.tvAiSummaryText)
    }
}
