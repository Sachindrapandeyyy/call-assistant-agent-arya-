package com.sachindra.callassistant

import android.app.Notification
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log

class CallNotificationListenerService : NotificationListenerService() {

    companion object {
        const val TAG = "[NOTIFICATION_LISTENER]"
        private val handler = Handler(Looper.getMainLooper())
        private var autoAnswerRunnable: Runnable? = null
        private var activeCallKey: String? = null
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)
        if (sbn == null) return

        val notification = sbn.notification ?: return
        val category = notification.category
        val isCallNotification = category == Notification.CATEGORY_CALL ||
                sbn.packageName.contains("dialer") ||
                sbn.packageName.contains("phone") ||
                sbn.packageName.contains("telecom") ||
                sbn.packageName.contains("truecaller") ||
                sbn.packageName.contains("transsion")

        if (!isCallNotification) return

        if (CallAssistantInCallService.currentActiveCall != null) {
            Log.d(TAG, "Call is already natively managed by CallAssistantInCallService. Skipping notification action.")
            return
        }

        val extras = notification.extras
        val title = extras.getString(Notification.EXTRA_TITLE) ?: ""
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""
        Log.d(TAG, "[NOTIFICATION] Call notification posted by ${sbn.packageName} -> Title: '$title', Text: '$text'")

        // Find the "Answer" action button inside the incoming call notification
        val actions = notification.actions ?: return
        var answerAction: Notification.Action? = null

        for (action in actions) {
            val actionTitle = action.title?.toString()?.lowercase() ?: ""
            Log.d(TAG, "[NOTIFICATION] Action found: '$actionTitle'")
            if (actionTitle.contains("answer") || actionTitle.contains("accept") || actionTitle.contains("pick") || actionTitle.contains("उठाएं") || actionTitle.contains("उत्तर")) {
                answerAction = action
                break
            }
        }

        // If no named answer action found, check if first action is Answer (standard Android telephony pattern)
        if (answerAction == null && actions.size >= 2) {
            // First action in Android CallStyle notification is typically Answer
            answerAction = actions[0]
        }

        if (answerAction != null) {
            val prefs = getSharedPreferences(MainActivity.PREFS_NAME, Context.MODE_PRIVATE)
            val autoAnswer = prefs.getBoolean(MainActivity.KEY_AUTO_ANSWER, true)
            val delayMs = prefs.getInt(MainActivity.KEY_DELAY_MS, 4000)

            val number = title.ifEmpty { "Incoming Caller" }
            activeCallKey = sbn.key

            // Send ringing event to PC WebSocket
            WebSocketTelephonyClient.sendEvent("incoming_call", mapOf(
                "number" to number,
                "state" to "RINGING",
                "delay_ms" to delayMs
            ))

            if (autoAnswer) {
                Log.d(TAG, "[TIMER] ⏱️ 4-SECOND COUNTDOWN STARTED for $number...")
                autoAnswerRunnable?.let { handler.removeCallbacks(it) }

                autoAnswerRunnable = Runnable {
                    try {
                        Log.d(TAG, "[ACTION] 🚀 4 SECONDS ELAPSED -> CLICKING NATIVE ANSWER ACTION BUTTON!")
                        answerAction.actionIntent.send()
                        Log.d(TAG, "[ACTION] Native Answer Action sent successfully!")

                        // Route call audio to Bluetooth Hands-Free (Phone Link)
                        try {
                            val audioManager = getSystemService(Context.AUDIO_SERVICE) as android.media.AudioManager
                            audioManager.mode = android.media.AudioManager.MODE_IN_CALL
                            audioManager.isBluetoothScoOn = true
                            audioManager.startBluetoothSco()
                            audioManager.isSpeakerphoneOn = false
                            Log.d(TAG, "[AUDIO] Requested Bluetooth SCO routing to Phone Link!")
                        } catch (e: Exception) {
                            Log.e(TAG, "Bluetooth routing note: ${e.message}")
                        }

                        WebSocketTelephonyClient.sendEvent("call_answered", mapOf(
                            "number" to number,
                            "state" to "ACTIVE"
                        ))
                    } catch (e: Exception) {
                        Log.e(TAG, "Error executing answer action: ${e.message}")
                    }
                }
                handler.postDelayed(autoAnswerRunnable!!, delayMs.toLong())
            }
        }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        super.onNotificationRemoved(sbn)
        if (sbn == null) return

        if (sbn.key == activeCallKey) {
            Log.d(TAG, "[NOTIFICATION] Call notification removed.")
            autoAnswerRunnable?.let { handler.removeCallbacks(it) }
            activeCallKey = null
        }
    }
}
