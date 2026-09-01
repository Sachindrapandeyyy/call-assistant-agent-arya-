package com.sachindra.callassistant

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

class FavoritesFragment : Fragment() {

    private lateinit var rvFavorites: RecyclerView
    private lateinit var adapter: ContactsAdapter

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        val view = inflater.inflate(R.layout.fragment_favorites, container, false)
        rvFavorites = view.findViewById(R.id.rvFavorites)
        rvFavorites.layoutManager = LinearLayoutManager(requireContext())

        adapter = ContactsAdapter(emptyList()) { contact ->
            PhoneUtils.placeOutgoingCall(requireContext(), contact.phone)
        }
        rvFavorites.adapter = adapter

        // Sample initial starred contacts
        val favorites = listOf(
            ContactModel("1", "Sachindra (Owner)", "+91 98765 43210"),
            ContactModel("2", "Harsh Sharma", "+91 91234 56789"),
            ContactModel("3", "Emergency Services", "112")
        )
        adapter.updateData(favorites)

        return view
    }
}
