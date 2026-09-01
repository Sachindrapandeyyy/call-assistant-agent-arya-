package com.sachindra.callassistant

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.TelephonyManager
import android.util.Log

class CallDiagnosticReceiver : BroadcastReceiver() {
    companion object {
        const val TAG = "[DIAGNOSTIC]"
    }

    override fun onReceive(context: Context?, intent: Intent?) {
        if (intent?.action == TelephonyManager.ACTION_PHONE_STATE_CHANGED) {
            val state = intent.getStringExtra(TelephonyManager.EXTRA_STATE)
            Log.d(TAG, "[CALL_STATE] Broadcast received: $state")
            
            // Optionally grab the number if permission granted, usually in EXTRA_INCOMING_NUMBER
            // We just log state changes for backup diagnostics here
        }
    }
}
