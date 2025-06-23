// MainActivity.kt
package com.example.zt

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.widget.CheckBox
import android.widget.EditText
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import com.example.zt.databinding.ActivityMainBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.prolificinteractive.materialcalendarview.CalendarDay
import org.threeten.bp.LocalDate
import org.threeten.bp.ZoneId
import java.util.*

// Extension для конвертации типа даты из календаря в java.util.Date для Room
fun LocalDate.toJavaUtilDate(): Date {
    val instant = this.atStartOfDay(ZoneId.systemDefault()).toInstant()
    // FIX: Date.from() требует API 26. Используем toEpochMilli() для совместимости.
    return Date(instant.toEpochMilli())
}

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val taskViewModel: TaskViewModel by viewModels()
    private lateinit var adapter: TaskAdapter
    // Храним ВЫБРАННУЮ пользователем дату, по умолчанию - сегодня
    private var selectedDate: Date = Date()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerView()
        setupCalendar()
        setupFab()
        observeViewModel()
    }

    private fun setupRecyclerView() {
        adapter = TaskAdapter(
            onTaskCheckedChanged = { task, isChecked ->
                taskViewModel.update(task.copy(isCompleted = isChecked))
            },
            onImportantClicked = { task ->
                taskViewModel.update(task.copy(isImportant = !task.isImportant))
            }
        )
        binding.recyclerView.adapter = adapter
    }

    private fun setupCalendar() {
        val calendarView = binding.calendarView

        // Устанавливаем русские сокращения для дней недели
        calendarView.setWeekDayLabels(arrayOf("ВС", "ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ"))

        // Слушатель смены даты
        calendarView.setOnDateChangedListener { _, day, _ ->
            // FIX: Сохраняем в локальную `val`, чтобы избежать smart cast-ошибок с mutable var
            val newDate = day.date.toJavaUtilDate()
            this.selectedDate = newDate
            taskViewModel.selectDate(newDate)
        }

        // FIX: Явно указываем, что устанавливаем свойство view, а не Activity.
        // Это решает ошибку type mismatch (Date vs CalendarDay).
        calendarView.selectedDate = CalendarDay.today()
    }

    private fun setupFab() {
        binding.fabAddTask.setOnClickListener { showAddTaskDialog() }
    }

    private fun observeViewModel() {
        taskViewModel.tasksForSelectedDate.observe(this) { tasks ->
            adapter.submitList(tasks)
            binding.emptyView.root.visibility = if (tasks.isEmpty()) View.VISIBLE else View.GONE
            binding.recyclerView.visibility = if (tasks.isEmpty()) View.GONE else View.VISIBLE
        }
    }

    private fun showAddTaskDialog() {
        val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_add_task, null)
        val editText = dialogView.findViewById<EditText>(R.id.editTextTaskTitle)
        val importantCheckBox = dialogView.findViewById<CheckBox>(R.id.checkboxImportant)

        MaterialAlertDialogBuilder(this)
            .setTitle("Новая задача")
            .setView(dialogView)
            .setPositiveButton("Добавить") { _, _ ->
                val title = editText.text.toString().trim()
                if (title.isNotBlank()) {
                    val newTask = Task(
                        title = title,
                        dueDate = selectedDate, // Используем сохраненную дату
                        isImportant = importantCheckBox.isChecked
                    )
                    taskViewModel.insert(newTask)
                }
            }
            .setNegativeButton("Отмена", null)
            .show()
    }
}