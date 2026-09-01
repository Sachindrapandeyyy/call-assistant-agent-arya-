package com.sachindra.callassistant

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.telecom.TelecomManager
import android.widget.Toast
import androidx.core.content.ContextCompat

object PhoneUtils {
    fun placeOutgoingCall(context: Context, phoneNumber: String) {
        val cleaned = phoneNumber.trim()
        if (cleaned.isEmpty()) return

        try {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
                val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$cleaned")).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
                return
            }

            val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as? TelecomManager
            if (telecomManager != null) {
                val uri = Uri.fromParts("tel", cleaned, null)
                val extras = Bundle()
                telecomManager.placeCall(uri, extras)
            } else {
                val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$cleaned")).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
            }
        } catch (e: SecurityException) {
            val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$cleaned")).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(context, "Error placing call: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }
}
