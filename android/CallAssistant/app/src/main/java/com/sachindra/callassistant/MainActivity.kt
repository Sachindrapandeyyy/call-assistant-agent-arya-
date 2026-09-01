package com.sachindra.callassistant

import android.Manifest
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import com.google.android.material.bottomnavigation.BottomNavigationView

class MainActivity : AppCompatActivity() {

    companion object {
        const val PREFS_NAME = "CallAssistantPrefs"
        const val KEY_AUTO_ANSWER = "auto_answer"
        const val KEY_DELAY_MS = "delay_ms"
        const val KEY_WS_HOST = "ws_host"
        const val KEY_WS_PORT = "ws_port"
        const val KEY_LAST_CALL = "key_last_call"
    }

    private lateinit var prefs: SharedPreferences
    private lateinit var bottomNavigation: BottomNavigationView

    private val favoritesFragment = FavoritesFragment()
    private val recentsFragment = RecentsFragment()
    private val contactsFragment = ContactsFragment()
    private val dialpadFragment = DialpadFragment()
    private val assistantFragment = AssistantFragment()

    private val requiredPermissions = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        arrayOf(
            Manifest.permission.ANSWER_PHONE_CALLS,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG,
            Manifest.permission.WRITE_CALL_LOG,
            Manifest.permission.READ_CONTACTS,
            Manifest.permission.CALL_PHONE,
            Manifest.permission.POST_NOTIFICATIONS
        )
    } else {
        arrayOf(
            Manifest.permission.ANSWER_PHONE_CALLS,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG,
            Manifest.permission.WRITE_CALL_LOG,
            Manifest.permission.READ_CONTACTS,
            Manifest.permission.CALL_PHONE
        )
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        if (hasAllPermissions()) {
            TelephonyService.startService(this)
            checkAndRequestDefaultDialer()
        }
    }

    private val roleManagerLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        // Default dialer request completed
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        bottomNavigation = findViewById(R.id.bottom_navigation)

        if (!hasAllPermissions()) {
            permissionLauncher.launch(requiredPermissions)
        } else {
            TelephonyService.startService(this)
            checkAndRequestDefaultDialer()
        }

        // Auto-connect to PC backend on launch
        val host = prefs.getString(KEY_WS_HOST, "192.168.29.205") ?: "192.168.29.205"
        val port = prefs.getInt(KEY_WS_PORT, 8000)
        WebSocketTelephonyClient.updateServerConfig(host, port)

        // Setup 5-tab Bottom Navigation
        setupBottomNavigation()

        // Default tab: Keypad (Dialpad) matching Image 1
        if (savedInstanceState == null) {
            bottomNavigation.selectedItemId = R.id.nav_dialpad
            loadFragment(dialpadFragment)
        }
    }

    private fun checkAndRequestDefaultDialer() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val roleManager = getSystemService(RoleManager::class.java)
            if (roleManager != null && roleManager.isRoleAvailable(RoleManager.ROLE_DIALER)) {
                if (!roleManager.isRoleHeld(RoleManager.ROLE_DIALER)) {
                    val intent = roleManager.createRequestRoleIntent(RoleManager.ROLE_DIALER)
                    roleManagerLauncher.launch(intent)
                }
            }
        }
    }

    private fun setupBottomNavigation() {
        bottomNavigation.setOnItemSelectedListener { item ->
            val fragment: Fragment = when (item.itemId) {
                R.id.nav_favorites -> favoritesFragment
                R.id.nav_recents -> recentsFragment
                R.id.nav_contacts -> contactsFragment
                R.id.nav_dialpad -> dialpadFragment
                R.id.nav_assistant -> assistantFragment
                else -> dialpadFragment
            }
            loadFragment(fragment)
            true
        }
    }

    private fun loadFragment(fragment: Fragment) {
        supportFragmentManager.beginTransaction()
            .replace(R.id.fragment_container, fragment)
            .commit()
    }

    private fun hasAllPermissions(): Boolean {
        for (p in requiredPermissions) {
            if (ContextCompat.checkSelfPermission(this, p) != PackageManager.PERMISSION_GRANTED) {
                return false
            }
        }
        return true
    }
}
