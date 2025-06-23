// App.kt
package com.example.zt

import android.app.Application
import com.jakewharton.threetenabp.AndroidThreeTen

// Инициализация библиотеки времени при старте приложения
class App : Application() {
    override fun onCreate() {
        super.onCreate()
        AndroidThreeTen.init(this)
    }
}