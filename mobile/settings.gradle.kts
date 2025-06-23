// settings.gradle.kts (Project)

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // Убедитесь, что эта строка на месте
        maven { url = uri("https://jitpack.io") }
    }
}
rootProject.name = "Zt" // Имя вашего проекта
include(":app")