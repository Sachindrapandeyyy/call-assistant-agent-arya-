package com.sachindra.callassistant

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.bluetooth.BluetoothDevice
import android.content.Context
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.telecom.Call
import android.telecom.CallAudioState
import android.telecom.InCallService
import android.telecom.VideoProfile
import android.util.Log
import androidx.core.app.NotificationCompat

class CallAssistantInCallService : InCallService() {

    companion object {
        const val TAG = "[CALL_SERVICE]"
        const val CHANNEL_ID = "call_assistant_channel"
        const val NOTIFICATION_ID = 1001
        var currentActiveCall: Call? = null
        var instance: CallAssistantInCallService? = null
    }

    private val handler = Handler(Looper.getMainLooper())
    private val callRunnables = mutableMapOf<Call, Runnable>()
    private var callStartTime = 0L

    override fun onCreate() {
        super.onCreate()
        instance = this
        createNotificationChannel()
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "AI Call Assistant Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Monitors and manages incoming call state for AI Assistant"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }
    }

    private fun showCallNotification(statusText: String) {
        val notification: Notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Aura AI Receptionist Active")
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.ic_menu_call)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

        val manager = getSystemService(NotificationManager::class.java)
        manager?.notify(NOTIFICATION_ID, notification)
    }

    private fun cancelCallNotification() {
        val manager = getSystemService(NotificationManager::class.java)
        manager?.cancel(NOTIFICATION_ID)
    }

    /**
     * Automatic audio routing monitor.
     * When Bluetooth (Lenovo LOQ / Phone Link) is supported, automatically forces route to Bluetooth!
     */
    override fun onCallAudioStateChanged(audioState: CallAudioState?) {
        super.onCallAudioStateChanged(audioState)
        if (audioState == null) return

        val currentRoute = audioState.route
        val supportedRoutes = audioState.supportedRouteMask
        val isBtSupported = (supportedRoutes and CallAudioState.ROUTE_BLUETOOTH) != 0

        Log.d(TAG, "[AUDIO ROUTE] Current: $currentRoute | SupportedMask: $supportedRoutes | BT Supported: $isBtSupported")

        if (isBtSupported && currentRoute != CallAudioState.ROUTE_BLUETOOTH) {
            Log.d(TAG, "[AUDIO ROUTE] 🚀 Actively switching call audio route to ROUTE_BLUETOOTH (Laptop)!")
            forceBluetoothRouting()
        }
    }

    fun forceBluetoothRouting() {
        try {
            setAudioRoute(CallAudioState.ROUTE_BLUETOOTH)
            Log.d(TAG, "[AUDIO ROUTE] setAudioRoute(ROUTE_BLUETOOTH) called successfully.")

            // Android 10+ specific Bluetooth device request
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val state = callAudioState
                if (state != null) {
                    for (device in state.supportedBluetoothDevices) {
                        Log.d(TAG, "[AUDIO ROUTE] Requesting Bluetooth Audio on device: ${device.name} (${device.address})")
                        requestBluetoothAudio(device)
                        break
                    }
                }
            }

            // Also request AudioManager SCO
            val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            audioManager.mode = AudioManager.MODE_IN_CALL
            audioManager.isBluetoothScoOn = true
            audioManager.startBluetoothSco()
            audioManager.isSpeakerphoneOn = false

        } catch (e: Exception) {
            Log.e(TAG, "Error forcing Bluetooth audio route: ${e.message}")
        }
    }

    private var isIncomingCall = false

    private val callCallback = object : Call.Callback() {
        override fun onStateChanged(call: Call, state: Int) {
            super.onStateChanged(call, state)
            val stateStr = callStateToString(state)
            val number = getCallerNumber(call)
            Log.d(TAG, "[CALL] State changed to: $stateStr for number: $number (Incoming: $isIncomingCall)")

            when (state) {
                Call.STATE_ACTIVE -> {
                    callStartTime = System.currentTimeMillis()
                    showCallNotification("Call connected: $number")

                    if (isIncomingCall) {
                        // Multi-stage retry to guarantee Bluetooth route locks in for AI Receptionist
                        forceBluetoothRouting()
                        handler.postDelayed({ forceBluetoothRouting() }, 300)
                        handler.postDelayed({ forceBluetoothRouting() }, 800)
                        handler.postDelayed({ forceBluetoothRouting() }, 1500)

                        WebSocketTelephonyClient.sendEvent("call_answered", mapOf(
                            "number" to number,
                            "state" to "ACTIVE"
                        ))
                    }
                }
                Call.STATE_DISCONNECTED -> {
                    cancelAutoAnswer(call)
                    cancelCallNotification()
                    val durationSec = if (callStartTime > 0) (System.currentTimeMillis() - callStartTime) / 1000.0 else 0.0
                    val disconnectCause = call.details.disconnectCause?.description?.toString() ?: "NORMAL"

                    WebSocketTelephonyClient.sendEvent("call_ended", mapOf(
                        "number" to number,
                        "duration" to durationSec,
                        "reason" to disconnectCause
                    ))
                    if (currentActiveCall == call) {
                        currentActiveCall = null
                    }
                }
                Call.STATE_RINGING -> {
                    showCallNotification("Incoming call: $number")
                }
            }
        }

        override fun onCallDestroyed(call: Call) {
            super.onCallDestroyed(call)
            Log.d(TAG, "[CALL] Call Destroyed")
            cancelCallNotification()
            if (currentActiveCall == call) {
                currentActiveCall = null
            }
        }
    }

    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        currentActiveCall = call
        val number = getCallerNumber(call)
        val stateStr = callStateToString(call.state)
        Log.d(TAG, "[CALL] onCallAdded from: $number, State: $stateStr")

        isIncomingCall = (call.state == Call.STATE_RINGING)
        val prefs = getSharedPreferences(MainActivity.PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(MainActivity.KEY_LAST_CALL, "$number (${java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault()).format(java.util.Date())})").apply()

        call.registerCallback(callCallback)

        // Launch in-call UI activity immediately to satisfy Android 13 Telecom
        try {
            val intent = android.content.Intent(this, InCallActivity::class.java).apply {
                flags = android.content.Intent.FLAG_ACTIVITY_NEW_TASK or
                        android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP or
                        android.content.Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            startActivity(intent)
        } catch (e: Exception) {
            Log.e(TAG, "Error launching InCallActivity: ${e.message}")
        }

        if (call.state == Call.STATE_RINGING) {
            showCallNotification("Incoming call: $number")
            val autoAnswer = prefs.getBoolean(MainActivity.KEY_AUTO_ANSWER, true)
            val delayMs = prefs.getInt(MainActivity.KEY_DELAY_MS, 4000)

            // Notify PC Backend
            WebSocketTelephonyClient.sendEvent("incoming_call", mapOf(
                "number" to number,
                "state" to "RINGING",
                "delay_ms" to delayMs
            ))

            if (autoAnswer) {
                Log.d(TAG, "[CALL] Scheduling auto-answer in ${delayMs}ms for $number")
                val runnable = Runnable {
                    if (call.state == Call.STATE_RINGING) {
                        Log.d(TAG, "[CALL] Answering audio call now for $number")
                        call.answer(VideoProfile.STATE_AUDIO_ONLY)

                        // Force audio route to Bluetooth (Laptop Phone Link)
                        handler.postDelayed({ forceBluetoothRouting() }, 300)
                        handler.postDelayed({ forceBluetoothRouting() }, 700)
                    }
                }
                callRunnables[call] = runnable
                handler.postDelayed(runnable, delayMs.toLong())
            }
        }
    }

    override fun onCallRemoved(call: Call) {
        super.onCallRemoved(call)
        Log.d(TAG, "[CALL] onCallRemoved")
        call.unregisterCallback(callCallback)
        cancelAutoAnswer(call)
        cancelCallNotification()
        if (currentActiveCall == call) {
            currentActiveCall = null
        }
    }

    private fun cancelAutoAnswer(call: Call) {
        callRunnables.remove(call)?.let {
            Log.d(TAG, "[CALL] Canceling auto-answer runnable")
            handler.removeCallbacks(it)
        }
    }

    private fun getCallerNumber(call: Call): String {
        return try {
            val handle = call.details.handle
            handle?.schemeSpecificPart ?: call.details.callerDisplayName ?: "Unknown"
        } catch (e: Exception) {
            "Unknown"
        }
    }

    private fun callStateToString(state: Int): String {
        return when (state) {
            Call.STATE_NEW -> "NEW"
            Call.STATE_RINGING -> "RINGING"
            Call.STATE_DIALING -> "DIALING"
            Call.STATE_ACTIVE -> "ACTIVE"
            Call.STATE_HOLDING -> "HOLDING"
            Call.STATE_DISCONNECTED -> "DISCONNECTED"
            Call.STATE_DISCONNECTING -> "DISCONNECTING"
            Call.STATE_CONNECTING -> "CONNECTING"
            else -> "UNKNOWN ($state)"
        }
    }
}
