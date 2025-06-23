// Database.kt
package com.example.zt

import android.content.Context
import androidx.lifecycle.LiveData
import androidx.room.*
import java.util.Date

@Entity(tableName = "tasks")
data class Task(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val title: String,
    val dueDate: Date,
    var isCompleted: Boolean = false,
    var isImportant: Boolean = false
)

class Converters {
    @TypeConverter
    fun fromTimestamp(value: Long?): Date? = value?.let { Date(it) }

    @TypeConverter
    fun dateToTimestamp(date: Date?): Long? = date?.time
}

@Dao
interface TaskDao {
    @Insert
    suspend fun insert(task: Task)

    @Update
    suspend fun update(task: Task)

    @Query("""
        SELECT * FROM tasks 
        WHERE dueDate = :date 
        ORDER BY isCompleted ASC, isImportant DESC, id DESC
    """)
    // Сортировка: сначала активные, среди них - важные, затем по дате добавления
    fun getTasksForDate(date: Date): LiveData<List<Task>>
}

@Database(entities = [Task::class], version = 3, exportSchema = false)
@TypeConverters(Converters::class)
abstract class AppDatabase : RoomDatabase() {

    abstract fun taskDao(): TaskDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                Room.databaseBuilder(context.applicationContext, AppDatabase::class.java, "task_database")
                    .fallbackToDestructiveMigration() // Для разработки: при смене схемы просто пересоздаем БД
                    .build()
                    .also { INSTANCE = it }
            }
        }
    }
}