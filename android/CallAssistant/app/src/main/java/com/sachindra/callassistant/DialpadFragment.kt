package com.sachindra.callassistant

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Bundle
import android.provider.ContactsContract
import android.view.HapticFeedbackConstants
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

class DialpadFragment : Fragment() {

    private lateinit var tvDialedNumber: TextView
    private lateinit var btnBackspace: ImageView
    private lateinit var btnCallAction: ImageButton
    private lateinit var rvT9Suggestions: RecyclerView

    private val currentNumber = StringBuilder()
    private var toneGenerator: ToneGenerator? = null
    private val allContacts = mutableListOf<ContactModel>()
    private lateinit var t9Adapter: ContactsAdapter

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        val view = inflater.inflate(R.layout.fragment_dialpad, container, false)

        try {
            toneGenerator = ToneGenerator(AudioManager.STREAM_DTMF, 70)
        } catch (e: Exception) {
            toneGenerator = null
        }

        tvDialedNumber = view.findViewById(R.id.tvDialedNumber)
        btnBackspace = view.findViewById(R.id.btnBackspace)
        btnCallAction = view.findViewById(R.id.btnCallAction)
        rvT9Suggestions = view.findViewById(R.id.rvT9Suggestions)

        rvT9Suggestions.layoutManager = LinearLayoutManager(requireContext(), LinearLayoutManager.HORIZONTAL, false)
        t9Adapter = ContactsAdapter(emptyList()) { contact ->
            PhoneUtils.placeOutgoingCall(requireContext(), contact.phone)
        }
        rvT9Suggestions.adapter = t9Adapter

        setupKeys(view)
        loadContactsForT9()

        btnBackspace.setOnClickListener { v ->
            v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
            if (currentNumber.isNotEmpty()) {
                currentNumber.deleteCharAt(currentNumber.length - 1)
                updateDisplay()
            }
        }

        btnBackspace.setOnLongClickListener { v ->
            v.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
            currentNumber.clear()
            updateDisplay()
            true
        }

        btnCallAction.setOnClickListener { v ->
            v.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
            val num = currentNumber.toString().trim()
            if (num.isNotEmpty()) {
                PhoneUtils.placeOutgoingCall(requireContext(), num)
            }
        }

        updateDisplay()
        return view
    }

    private fun setupKeys(root: View) {
        val keyToneMap = mapOf(
            R.id.btnKey1 to Pair("1", ToneGenerator.TONE_DTMF_1),
            R.id.btnKey2 to Pair("2", ToneGenerator.TONE_DTMF_2),
            R.id.btnKey3 to Pair("3", ToneGenerator.TONE_DTMF_3),
            R.id.btnKey4 to Pair("4", ToneGenerator.TONE_DTMF_4),
            R.id.btnKey5 to Pair("5", ToneGenerator.TONE_DTMF_5),
            R.id.btnKey6 to Pair("6", ToneGenerator.TONE_DTMF_6),
            R.id.btnKey7 to Pair("7", ToneGenerator.TONE_DTMF_7),
            R.id.btnKey8 to Pair("8", ToneGenerator.TONE_DTMF_8),
            R.id.btnKey9 to Pair("9", ToneGenerator.TONE_DTMF_9),
            R.id.btnKey0 to Pair("0", ToneGenerator.TONE_DTMF_0),
            R.id.btnKeyStar to Pair("*", ToneGenerator.TONE_DTMF_S),
            R.id.btnKeyHash to Pair("#", ToneGenerator.TONE_DTMF_P)
        )

        for ((id, pair) in keyToneMap) {
            val (digit, tone) = pair
            root.findViewById<Button>(id)?.setOnClickListener { v ->
                v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                try {
                    toneGenerator?.startTone(tone, 120)
                } catch (e: Exception) {}
                currentNumber.append(digit)
                updateDisplay()
            }
        }

        // Long-press 0 for '+'
        root.findViewById<Button>(R.id.btnKey0)?.setOnLongClickListener { v ->
            v.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
            currentNumber.append("+")
            updateDisplay()
            true
        }

        // Long-press 1 for Voicemail
        root.findViewById<Button>(R.id.btnKey1)?.setOnLongClickListener { v ->
            v.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
            PhoneUtils.placeOutgoingCall(requireContext(), "123")
            true
        }
    }

    private fun loadContactsForT9() {
        val context = context ?: return
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
            return
        }

        try {
            val cursor = context.contentResolver.query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                arrayOf(
                    ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    ContactsContract.CommonDataKinds.Phone.NUMBER
                ),
                null, null, "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} ASC"
            )

            allContacts.clear()
            cursor?.use {
                val nameIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                val numIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
                while (it.moveToNext()) {
                    val name = if (nameIdx != -1) it.getString(nameIdx) ?: "Unknown" else "Unknown"
                    val num = if (numIdx != -1) it.getString(numIdx) ?: "" else ""
                    if (num.isNotEmpty()) {
                        allContacts.add(ContactModel("", name, num))
                    }
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun updateDisplay() {
        val dialed = currentNumber.toString()
        tvDialedNumber.text = dialed
        if (dialed.isNotEmpty()) {
            btnBackspace.visibility = View.VISIBLE
            filterT9Contacts(dialed)
        } else {
            btnBackspace.visibility = View.INVISIBLE
            rvT9Suggestions.visibility = View.GONE
        }
    }

    private fun filterT9Contacts(query: String) {
        val cleanQuery = query.replace("+", "").trim()
        if (cleanQuery.isEmpty()) {
            rvT9Suggestions.visibility = View.GONE
            return
        }

        val filtered = allContacts.filter { contact ->
            val cleanPhone = contact.phone.replace(" ", "").replace("-", "")
            cleanPhone.contains(cleanQuery) || contact.name.lowercase().contains(cleanQuery.lowercase())
        }.take(8)

        if (filtered.isNotEmpty()) {
            rvT9Suggestions.visibility = View.VISIBLE
            t9Adapter.updateData(filtered)
        } else {
            rvT9Suggestions.visibility = View.GONE
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        toneGenerator?.release()
        toneGenerator = null
    }
}
