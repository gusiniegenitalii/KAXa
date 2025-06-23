// TaskAdapter.kt
package com.example.zt

import android.graphics.Paint
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.CheckBox
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView

class TaskAdapter(
    private val onTaskCheckedChanged: (Task, Boolean) -> Unit,
    private val onImportantClicked: (Task) -> Unit
) : ListAdapter<Task, TaskAdapter.TaskViewHolder>(TaskDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): TaskViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_task, parent, false)
        return TaskViewHolder(view)
    }

    override fun onBindViewHolder(holder: TaskViewHolder, position: Int) {
        holder.bind(getItem(position), onTaskCheckedChanged, onImportantClicked)
    }

    class TaskViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val titleTextView: TextView = itemView.findViewById(R.id.textViewTitle)
        private val completedCheckBox: CheckBox = itemView.findViewById(R.id.checkboxCompleted)
        private val importantImageView: ImageView = itemView.findViewById(R.id.imageButtonImportant)

        fun bind(task: Task, onTaskCheckedChanged: (Task, Boolean) -> Unit, onImportantClicked: (Task) -> Unit) {
            titleTextView.text = task.title

            // Отвязываем слушатель, чтобы не сработал от переиспользования View
            completedCheckBox.setOnCheckedChangeListener(null)
            completedCheckBox.isChecked = task.isCompleted
            // Возвращаем слушатель для реакции на действия пользователя
            completedCheckBox.setOnCheckedChangeListener { _, isChecked -> onTaskCheckedChanged(task, isChecked) }

            titleTextView.paintFlags = if (task.isCompleted) {
                titleTextView.paintFlags or Paint.STRIKE_THRU_TEXT_FLAG
            } else {
                titleTextView.paintFlags and Paint.STRIKE_THRU_TEXT_FLAG.inv()
            }

            val starIcon = if (task.isImportant) R.drawable.ic_important_filled else R.drawable.ic_important_outline
            importantImageView.setImageResource(starIcon)
            importantImageView.setOnClickListener { onImportantClicked(task) }
        }
    }
}

class TaskDiffCallback : DiffUtil.ItemCallback<Task>() {
    override fun areItemsTheSame(oldItem: Task, newItem: Task): Boolean = oldItem.id == newItem.id
    // Сравнение по контенту, data class `equals` делает это за нас
    override fun areContentsTheSame(oldItem: Task, newItem: Task): Boolean = oldItem == newItem
}