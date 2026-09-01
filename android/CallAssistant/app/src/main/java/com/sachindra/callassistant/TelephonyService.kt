package com.sachindra.callassistant

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.telecom.TelecomManager
import android.telephony.PhoneStateListener
import android.telephony.TelephonyCallback
import android.telephony.TelephonyManager
import android.util.Log
import android.view.KeyEvent
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat

class TelephonyService : Service() {

    companion object {
        const val TAG = "[TELEPHONY_SRV]"
        const val CHANNEL_ID = "telephony_service_channel"
        const val NOTIFICATION_ID = 2001

        fun startService(context: Context) {
            try {
                val intent = Intent(context, TelephonyService::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error starting TelephonyService: ${e.message}")
            }
        }
    }

    private val handler = Handler(Looper.getMainLooper())
    private var autoAnswerRunnable: Runnable? = null
    private var currentRingingNumber: String? = null
    private var isCallActive = false
    private var isListenerRegistered = false

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification("AI Call Assistant active"))
        registerTelephonyListenerIfPermitted()
        Log.d(TAG, "TelephonyService initialized.")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        registerTelephonyListenerIfPermitted()
        return START_STICKY
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "AI Assistant Telephony Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Monitors and auto-answers incoming phone calls"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("AI Call Assistant Active")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_call)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager?.notify(NOTIFICATION_ID, buildNotification(text))
    }

    private fun registerTelephonyListenerIfPermitted() {
        if (isListenerRegistered) return

        val hasPermission = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.READ_PHONE_STATE
        ) == PackageManager.PERMISSION_GRANTED

        if (!hasPermission) {
            Log.w(TAG, "READ_PHONE_STATE not granted yet.")
            return
        }

        try {
            val telephonyManager = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                telephonyManager.registerTelephonyCallback(
                    mainExecutor,
                    object : TelephonyCallback(), TelephonyCallback.CallStateListener {
                        override fun onCallStateChanged(state: Int) {
                            handleCallState(state, null)
                        }
                    }
                )
            } else {
                @Suppress("DEPRECATION")
                telephonyManager.listen(object : PhoneStateListener() {
                    @Deprecated("Deprecated in Java")
                    override fun onCallStateChanged(state: Int, phoneNumber: String?) {
                        handleCallState(state, phoneNumber)
                    }
                }, PhoneStateListener.LISTEN_CALL_STATE)
            }
            isListenerRegistered = true
            Log.d(TAG, "TelephonyListener registered successfully.")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to register telephony listener: ${e.message}")
        }
    }

    fun handleCallState(state: Int, incomingNumber: String?) {
        val number = incomingNumber ?: currentRingingNumber ?: "Unknown"
        val prefs = getSharedPreferences(MainActivity.PREFS_NAME, Context.MODE_PRIVATE)

        when (state) {
            TelephonyManager.CALL_STATE_RINGING -> {
                currentRingingNumber = incomingNumber
                isCallActive = false
                Log.d(TAG, "[CALL] Incoming ringing call from: $number")
                updateNotification("Incoming Call from $number")

                val autoAnswer = prefs.getBoolean(MainActivity.KEY_AUTO_ANSWER, true)
                val delayMs = prefs.getInt(MainActivity.KEY_DELAY_MS, 4000)

                WebSocketTelephonyClient.sendEvent("incoming_call", mapOf(
                    "number" to number,
                    "state" to "RINGING",
                    "delay_ms" to delayMs
                ))

                if (autoAnswer) {
                    Log.d(TAG, "[CALL] Scheduling multi-strategy auto-answer in ${delayMs}ms")
                    autoAnswerRunnable?.let { handler.removeCallbacks(it) }
                    
                    autoAnswerRunnable = Runnable {
                        Log.d(TAG, "[CALL] Answering call via TelecomManager & Headset Hook...")
                        answerCallMultiStrategy()
                    }
                    handler.postDelayed(autoAnswerRunnable!!, delayMs.toLong())
                }
            }

            TelephonyManager.CALL_STATE_OFFHOOK -> {
                Log.d(TAG, "[CALL] Call state OFFHOOK (Active Call)")
                autoAnswerRunnable?.let { handler.removeCallbacks(it) }
                isCallActive = true
                updateNotification("Call connected: $number")

                WebSocketTelephonyClient.sendEvent("call_answered", mapOf(
                    "number" to number,
                    "state" to "ACTIVE"
                ))
            }

            TelephonyManager.CALL_STATE_IDLE -> {
                Log.d(TAG, "[CALL] Call state IDLE (Call Ended)")
                autoAnswerRunnable?.let { handler.removeCallbacks(it) }
                updateNotification("AI Call Assistant active")

                if (isCallActive) {
                    WebSocketTelephonyClient.sendEvent("call_ended", mapOf(
                        "number" to number,
                        "state" to "IDLE"
                    ))
                    isCallActive = false
                }
                currentRingingNumber = null
            }
        }
    }

    private fun answerCallMultiStrategy() {
        // Strategy 1: Android TelecomManager system API
        try {
            val telecomManager = getSystemService(Context.TELECOM_SERVICE) as TelecomManager
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.ANSWER_PHONE_CALLS) == PackageManager.PERMISSION_GRANTED) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    telecomManager.acceptRingingCall()
                    Log.d(TAG, "[CALL] TelecomManager.acceptRingingCall() triggered.")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "[CALL] TelecomManager error: ${e.message}")
        }

        // Strategy 2: Headset Hook Media Key event (Bypasses Truecaller / Overlay restrictions)
        try {
            val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val downEvent = KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_HEADSETHOOK)
            val upEvent = KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_HEADSETHOOK)
            audioManager.dispatchMediaKeyEvent(downEvent)
            audioManager.dispatchMediaKeyEvent(upEvent)
            Log.d(TAG, "[CALL] Dispatched KEYCODE_HEADSETHOOK to AudioManager.")
        } catch (e: Exception) {
            Log.e(TAG, "[CALL] Headset hook dispatch note: ${e.message}")
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        autoAnswerRunnable?.let { handler.removeCallbacks(it) }
    }
}
