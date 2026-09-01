package com.sachindra.callassistant

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.ContactsContract
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.ImageView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

class ContactsFragment : Fragment() {

    private lateinit var etSearchContacts: EditText
    private lateinit var rvContacts: RecyclerView
    private lateinit var adapter: ContactsAdapter

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        val view = inflater.inflate(R.layout.fragment_contacts, container, false)
        etSearchContacts = view.findViewById(R.id.etSearchContacts)
        rvContacts = view.findViewById(R.id.rvContacts)

        rvContacts.layoutManager = LinearLayoutManager(requireContext())
        adapter = ContactsAdapter(emptyList()) { contact ->
            dialNumber(contact.phone)
        }
        rvContacts.adapter = adapter

        etSearchContacts.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                adapter.filter(s?.toString() ?: "")
            }
            override fun afterTextChanged(s: Editable?) {}
        })

        val btnAddContact: ImageView = view.findViewById(R.id.btnAddContact)
        btnAddContact.setOnClickListener {
            val intent = Intent(Intent.ACTION_INSERT, ContactsContract.Contacts.CONTENT_URI)
            startActivity(intent)
        }

        loadContacts()
        return view
    }

    override fun onResume() {
        super.onResume()
        loadContacts()
    }

    private fun loadContacts() {
        val context = context ?: return
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
            return
        }

        val contacts = mutableListOf<ContactModel>()
        val seenPhones = mutableSetOf<String>()

        try {
            val cursor = context.contentResolver.query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                arrayOf(
                    ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    ContactsContract.CommonDataKinds.Phone.NUMBER
                ),
                null,
                null,
                "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} ASC"
            )

            cursor?.use {
                val idIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.CONTACT_ID)
                val nameIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                val numIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)

                while (it.moveToNext()) {
                    val id = if (idIdx != -1) it.getString(idIdx) else ""
                    val name = if (nameIdx != -1) it.getString(nameIdx) else "Unknown"
                    val phone = if (numIdx != -1) it.getString(numIdx) else ""

                    val normalized = phone.replace(" ", "").replace("-", "")
                    if (normalized.isNotEmpty() && !seenPhones.contains(normalized)) {
                        seenPhones.add(normalized)
                        contacts.add(ContactModel(id, name, phone))
                    }
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }

        adapter.updateData(contacts)
    }

    private fun dialNumber(number: String) {
        PhoneUtils.placeOutgoingCall(requireContext(), number)
    }
}
