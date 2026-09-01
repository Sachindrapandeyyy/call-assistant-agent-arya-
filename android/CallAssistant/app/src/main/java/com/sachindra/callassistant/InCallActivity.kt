package com.sachindra.callassistant

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.telecom.Call
import android.telecom.CallAudioState
import android.telecom.VideoProfile
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class InCallActivity : AppCompatActivity() {

    private lateinit var tvCallStatus: TextView
    private lateinit var tvCallTimer: TextView

    // Incoming View
    private lateinit var llIncomingCenterView: LinearLayout
    private lateinit var tvAvatarInitials: TextView
    private lateinit var tvCallerName: TextView
    private lateinit var tvCallerNumber: TextView

    // Active In-Call View
    private lateinit var llActiveCenterView: LinearLayout
    private lateinit var tvActiveCallerName: TextView

    // 2x3 Actions
    private lateinit var btnActionQuickSms: LinearLayout
    private lateinit var btnActionTakeover: LinearLayout
    private lateinit var ivAiModeIcon: ImageView
    private lateinit var tvAiModeText: TextView

    private lateinit var btnActionMute: LinearLayout
    private lateinit var ivMuteIcon: ImageView
    private lateinit var tvMuteText: TextView

    private lateinit var btnActionAudioRoute: LinearLayout
    private lateinit var ivAudioRouteIcon: ImageView
    private lateinit var tvAudioRouteText: TextView

    private lateinit var btnActionHold: LinearLayout
    private lateinit var ivHoldIcon: ImageView
    private lateinit var tvHoldText: TextView

    private lateinit var btnActionKeypad: LinearLayout

    // Keypad Overlay
    private lateinit var llDtmfOverlay: LinearLayout
    private lateinit var tvDtmfDisplay: TextView
    private lateinit var btnHideDtmf: Button

    // Bottom Controls
    private lateinit var llIncomingRow: LinearLayout
    private lateinit var btnAnswerCall: ImageView
    private lateinit var btnRejectCall: ImageView

    private lateinit var llActiveBottomCard: LinearLayout
    private lateinit var btnEndCallContainer: LinearLayout
    private lateinit var tvBottomButtonText: TextView
    private lateinit var tvBottomPhoneNumber: TextView

    private var isMuted = false
    private var isHeld = false
    private var isSpeakerOn = false
    private var callStartTime = 0L
    private val dtmfBuilder = StringBuilder()

    private val timerHandler = Handler(Looper.getMainLooper())
    private val timerRunnable = object : Runnable {
        override fun run() {
            if (callStartTime > 0) {
                val elapsedSec = (System.currentTimeMillis() - callStartTime) / 1000
                val mins = elapsedSec / 60
                val secs = elapsedSec % 60
                val timeStr = String.format("%02d:%02d", mins, secs)
                tvCallTimer.text = timeStr
                tvCallStatus.text = "CONNECTED ()"
                timerHandler.postDelayed(this, 1000)
            }
        }
    }

    private val callCallback = object : Call.Callback() {
        override fun onStateChanged(call: Call, state: Int) {
            super.onStateChanged(call, state)
            runOnUiThread {
                updateCallState(call, state)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        window.addFlags(
            WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
            WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD or
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
            WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
        )

        setContentView(R.layout.activity_in_call)
        initViews()

        val call = CallAssistantInCallService.currentActiveCall
        if (call == null || call.state == Call.STATE_DISCONNECTED) {
            finish()
            return
        }

        call.registerCallback(callCallback)
        updateCallState(call, call.state)
        setupActionListeners()
    }

    private fun initViews() {
        tvCallStatus = findViewById(R.id.tvCallStatus)
        tvCallTimer = findViewById(R.id.tvCallTimer)

        llIncomingCenterView = findViewById(R.id.llIncomingCenterView)
        tvAvatarInitials = findViewById(R.id.tvAvatarInitials)
        tvCallerName = findViewById(R.id.tvCallerName)
        tvCallerNumber = findViewById(R.id.tvCallerNumber)

        llActiveCenterView = findViewById(R.id.llActiveCenterView)
        tvActiveCallerName = findViewById(R.id.tvActiveCallerName)

        btnActionQuickSms = findViewById(R.id.btnActionQuickSms)
        btnActionTakeover = findViewById(R.id.btnActionTakeover)
        ivAiModeIcon = findViewById(R.id.ivAiModeIcon)
        tvAiModeText = findViewById(R.id.tvAiModeText)

        btnActionMute = findViewById(R.id.btnActionMute)
        ivMuteIcon = findViewById(R.id.ivMuteIcon)
        tvMuteText = findViewById(R.id.tvMuteText)

        btnActionAudioRoute = findViewById(R.id.btnActionAudioRoute)
        ivAudioRouteIcon = findViewById(R.id.ivAudioRouteIcon)
        tvAudioRouteText = findViewById(R.id.tvAudioRouteText)

        btnActionHold = findViewById(R.id.btnActionHold)
        ivHoldIcon = findViewById(R.id.ivHoldIcon)
        tvHoldText = findViewById(R.id.tvHoldText)

        btnActionKeypad = findViewById(R.id.btnActionKeypad)

        llDtmfOverlay = findViewById(R.id.llDtmfOverlay)
        tvDtmfDisplay = findViewById(R.id.tvDtmfDisplay)
        btnHideDtmf = findViewById(R.id.btnHideDtmf)

        llIncomingRow = findViewById(R.id.llIncomingRow)
        btnAnswerCall = findViewById(R.id.btnAnswerCall)
        btnRejectCall = findViewById(R.id.btnRejectCall)

        llActiveBottomCard = findViewById(R.id.llActiveBottomCard)
        btnEndCallContainer = findViewById(R.id.btnEndCallContainer)
        tvBottomButtonText = findViewById(R.id.tvBottomButtonText)
        tvBottomPhoneNumber = findViewById(R.id.tvBottomPhoneNumber)
    }

    private fun setupActionListeners() {
        // End Call from Bottom Card
        btnEndCallContainer.setOnClickListener {
            CallAssistantInCallService.currentActiveCall?.disconnect()
            finish()
        }

        // Incoming Answer
        btnAnswerCall.setOnClickListener {
            CallAssistantInCallService.currentActiveCall?.answer(VideoProfile.STATE_AUDIO_ONLY)
        }

        // Incoming Reject
        btnRejectCall.setOnClickListener {
            CallAssistantInCallService.currentActiveCall?.reject(false, null)
            finish()
        }

        // Mute / Unmute
        btnActionMute.setOnClickListener {
            val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            isMuted = !isMuted
            audioManager.isMicrophoneMute = isMuted
            tvMuteText.text = if (isMuted) "unmute" else "mute"
            ivMuteIcon.alpha = if (isMuted) 0.5f else 1.0f
            Toast.makeText(this, if (isMuted) "Microphone Muted" else "Microphone Unmuted", Toast.LENGTH_SHORT).show()
        }

        // Speaker / Audio Route (List / Speaker)
        btnActionAudioRoute.setOnClickListener {
            val service = CallAssistantInCallService.instance
            isSpeakerOn = !isSpeakerOn
            if (isSpeakerOn) {
                service?.setAudioRoute(CallAudioState.ROUTE_SPEAKER)
                tvAudioRouteText.text = "earpiece"
                Toast.makeText(this, "Audio: Speakerphone 🔊", Toast.LENGTH_SHORT).show()
            } else {
                service?.setAudioRoute(CallAudioState.ROUTE_EARPIECE)
                tvAudioRouteText.text = "list"
                Toast.makeText(this, "Audio: Earpiece 📱", Toast.LENGTH_SHORT).show()
            }
        }

        // Remind Me / Hold
        btnActionHold.setOnClickListener {
            val activeCall = CallAssistantInCallService.currentActiveCall
            if (activeCall != null) {
                isHeld = !isHeld
                if (isHeld) {
                    activeCall.hold()
                    tvHoldText.text = "resume"
                    tvCallStatus.text = "CALL ON HOLD"
                } else {
                    activeCall.unhold()
                    tvHoldText.text = "remind me"
                    tvCallStatus.text = "ACTIVE CALL"
                }
            }
        }

        // Record / Takeover / Aura AI mode
        btnActionTakeover.setOnClickListener {
            Toast.makeText(this, "Aura AI Active Call Screen", Toast.LENGTH_SHORT).show()
        }

        // Keyboard DTMF Keypad Toggle
        btnActionKeypad.setOnClickListener {
            llDtmfOverlay.visibility = View.VISIBLE
            llActiveCenterView.visibility = View.GONE
        }

        btnHideDtmf.setOnClickListener {
            llDtmfOverlay.visibility = View.GONE
            llActiveCenterView.visibility = View.VISIBLE
        }

        setupDtmfKeys()

        // Quick Message / SMS
        btnActionQuickSms.setOnClickListener {
            val number = tvCallerNumber.text.toString().trim()
            val smsIntent = Intent(Intent.ACTION_SENDTO).apply {
                data = Uri.parse("smsto:")
                putExtra("sms_body", "Can't talk right now. Please message or I'll call you back shortly.")
            }
            CallAssistantInCallService.currentActiveCall?.reject(false, null)
            startActivity(smsIntent)
            finish()
        }
    }

    private fun setupDtmfKeys() {
        val dtmfMap = mapOf(
            R.id.btnDtmf1 to '1', R.id.btnDtmf2 to '2', R.id.btnDtmf3 to '3',
            R.id.btnDtmf4 to '4', R.id.btnDtmf5 to '5', R.id.btnDtmf6 to '6',
            R.id.btnDtmf7 to '7', R.id.btnDtmf8 to '8', R.id.btnDtmf9 to '9',
            R.id.btnDtmfStar to '*', R.id.btnDtmf0 to '0', R.id.btnDtmfHash to '#'
        )

        for ((id, char) in dtmfMap) {
            findViewById<Button>(id)?.setOnClickListener {
                dtmfBuilder.append(char)
                tvDtmfDisplay.text = dtmfBuilder.toString()
                CallAssistantInCallService.currentActiveCall?.playDtmfTone(char)
                Handler(Looper.getMainLooper()).postDelayed({
                    CallAssistantInCallService.currentActiveCall?.stopDtmfTone()
                }, 200)
            }
        }
    }

    private fun updateCallState(call: Call, state: Int) {
        val number = try {
            call.details.handle?.schemeSpecificPart ?: call.details.callerDisplayName ?: "Unknown Caller"
        } catch (e: Exception) {
            "Unknown Caller"
        }
        val name = call.details.callerDisplayName ?: number
        tvCallerName.text = name
        tvCallerNumber.text = number
        tvActiveCallerName.text = name
        tvBottomPhoneNumber.text = number

        val initial = if (name.isNotEmpty() && name[0].isLetter()) name[0].uppercase() else "?"
        tvAvatarInitials.text = initial

        when (state) {
            Call.STATE_RINGING -> {
                tvCallStatus.text = "CALLING..."
                llIncomingCenterView.visibility = View.VISIBLE
                llActiveCenterView.visibility = View.GONE
                llIncomingRow.visibility = View.VISIBLE
                llActiveBottomCard.visibility = View.GONE
            }
            Call.STATE_DIALING, Call.STATE_CONNECTING -> {
                tvCallStatus.text = "CALLING..."
                llIncomingCenterView.visibility = View.GONE
                llActiveCenterView.visibility = View.VISIBLE
                llIncomingRow.visibility = View.GONE
                llActiveBottomCard.visibility = View.VISIBLE
                tvBottomButtonText.text = "End Call"
            }
            Call.STATE_ACTIVE -> {
                llIncomingCenterView.visibility = View.GONE
                llActiveCenterView.visibility = View.VISIBLE
                llIncomingRow.visibility = View.GONE
                llActiveBottomCard.visibility = View.VISIBLE
                tvBottomButtonText.text = "End Call"
                if (callStartTime == 0L) {
                    callStartTime = System.currentTimeMillis()
                    timerHandler.post(timerRunnable)
                }
            }
            Call.STATE_DISCONNECTED -> {
                tvCallStatus.text = "CALL ENDED"
                tvBottomButtonText.text = "Call back"
                timerHandler.removeCallbacks(timerRunnable)
                Handler(Looper.getMainLooper()).postDelayed({
                    finish()
                }, 1200)
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        timerHandler.removeCallbacks(timerRunnable)
    }
}
