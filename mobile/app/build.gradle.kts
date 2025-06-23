// build.gradle.kts (Module :app)

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    // УБЕДИТЕСЬ, ЧТО ЭТА СТРОКА ЕСТЬ
    id("com.google.devtools.ksp")
}

android {
    namespace = "com.example.zt" // У вас может быть другое имя пакета
    compileSdk = 34 // или 35, не так важно

    defaultConfig {
        applicationId = "com.example.zt"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    kotlinOptions {
        jvmTarget = "1.8"
    }
    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    // Стандартные зависимости
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")

    // Календарь
    implementation("com.github.prolificinteractive:material-calendarview:2.0.1")
    implementation("com.jakewharton.threetenabp:threetenabp:1.4.6")

    // RecyclerView
    implementation("androidx.recyclerview:recyclerview:1.3.2")

    // ViewModel и LiveData
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-livedata-ktx:2.7.0")
    implementation("androidx.activity:activity-ktx:1.8.2")

    // --- ВНИМАНИЕ НА ЭТОТ БЛОК ---
    // Room для базы данных
    val room_version = "2.6.1"
    implementation("androidx.room:room-runtime:$room_version")
    // УБЕДИТЕСЬ, ЧТО У ВАС ИМЕННО ЭТА СТРОКА, А НЕ annotationProcessor
    ksp("androidx.room:room-compiler:$room_version")
    implementation("androidx.room:room-ktx:$room_version")
    // ----------------------------
    testImplementation("junit:junit:4.13.2")

    // Зависимости для ИНСТРУМЕНТАЛЬНЫХ тестов (на устройстве/эмуляторе)
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
}
