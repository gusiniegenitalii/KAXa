// TaskViewModel.kt
package com.example.zt

import android.app.Application
import androidx.lifecycle.*
import kotlinx.coroutines.launch
import java.util.Calendar
import java.util.Date

class TaskViewModel(application: Application) : AndroidViewModel(application) {

    private val taskDao: TaskDao = AppDatabase.getDatabase(application).taskDao()
    private val _selectedDate = MutableLiveData<Date>()

    // switchMap автоматически переключает источник LiveData при смене даты
    val tasksForSelectedDate: LiveData<List<Task>> = _selectedDate.switchMap { date ->
        taskDao.getTasksForDate(date)
    }

    init {
        // Изначально показываем задачи на сегодня
        selectDate(Date())
    }

    fun selectDate(date: Date) {
        _selectedDate.value = getStartOfDay(date)
    }

    fun insert(task: Task) = viewModelScope.launch {
        taskDao.insert(task)
    }

    fun update(task: Task) = viewModelScope.launch {
        taskDao.update(task)
    }

    // Нормализуем дату, убирая время, для корректного запроса в БД
    private fun getStartOfDay(date: Date): Date {
        return Calendar.getInstance().apply {
            time = date
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }.time
    }
}