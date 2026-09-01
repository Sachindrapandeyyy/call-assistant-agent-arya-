package com.sachindra.callassistant

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

class ContactsAdapter(
    private var allContacts: List<ContactModel>,
    private val onContactClicked: (ContactModel) -> Unit
) : RecyclerView.Adapter<ContactsAdapter.ContactViewHolder>() {

    private var filteredContacts: List<ContactModel> = allContacts

    private val gradientDrawables = intArrayOf(
        R.drawable.bg_galaxy_avatar_nebula,
        R.drawable.bg_galaxy_avatar_supernova,
        R.drawable.bg_galaxy_avatar_solar
    )

    fun updateData(newContacts: List<ContactModel>) {
        allContacts = newContacts.sortedBy { it.name.lowercase() }
        filteredContacts = allContacts
        notifyDataSetChanged()
    }

    fun filter(query: String) {
        filteredContacts = if (query.isEmpty()) {
            allContacts
        } else {
            val q = query.lowercase().trim()
            allContacts.filter {
                it.name.lowercase().contains(q) || it.phone.replace(" ", "").contains(q)
            }
        }
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ContactViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_contact, parent, false)
        return ContactViewHolder(view)
    }

    override fun onBindViewHolder(holder: ContactViewHolder, position: Int) {
        val contact = filteredContacts[position]
        holder.tvContactName.text = contact.name
        holder.tvContactPhone.text = "Mobile • ${contact.phone}"

        val initial = if (contact.name.isNotEmpty()) contact.name.first().uppercase() else "👤"
        holder.tvContactInitial.text = initial

        val gradIdx = Math.abs(contact.name.hashCode()) % gradientDrawables.size
        holder.tvContactInitial.setBackgroundResource(gradientDrawables[gradIdx])
        holder.tvContactInitial.background?.setTintList(null)

        holder.btnCallContact.setOnClickListener {
            onContactClicked(contact)
        }

        holder.itemView.setOnClickListener {
            onContactClicked(contact)
        }
    }

    override fun getItemCount(): Int = filteredContacts.size

    class ContactViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val tvContactInitial: TextView = view.findViewById(R.id.tvContactInitial)
        val tvContactName: TextView = view.findViewById(R.id.tvContactName)
        val tvContactPhone: TextView = view.findViewById(R.id.tvContactPhone)
        val btnCallContact: ImageView = view.findViewById(R.id.btnCallContact)
    }
}
