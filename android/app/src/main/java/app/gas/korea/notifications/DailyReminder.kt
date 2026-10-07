package app.gas.korea.notifications

import android.Manifest
import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import app.gas.korea.MainActivity
import app.gas.korea.R
import java.time.ZonedDateTime

object DailyReminder {
    private const val ACTION = "app.gas.korea.DAILY_REMINDER"
    private const val CHANNEL = "daily_polls"
    private fun prefs(context: Context) = context.getSharedPreferences("gas.settings", 0)
    fun enabled(context: Context) = prefs(context).getBoolean("reminder", false)
    fun permitted(context: Context): Boolean = context.getSystemService(NotificationManager::class.java).areNotificationsEnabled() &&
        (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED)
    private fun pending(context: Context) = PendingIntent.getBroadcast(context, 20,
        Intent(context, ReminderReceiver::class.java).setAction(ACTION), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    fun enable(context: Context) {
        check(permitted(context)) { "Allow notifications in Android Settings to enable reminders." }
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL, "Daily poll reminder", NotificationManager.IMPORTANCE_DEFAULT))
        prefs(context).edit().putBoolean("reminder", true).apply(); schedule(context)
    }
    fun schedule(context: Context) {
        if (!enabled(context)) return
        val now = ZonedDateTime.now()
        var next = now.withHour(20).withMinute(0).withSecond(0).withNano(0)
        if (!next.isAfter(now)) next = next.plusDays(1)
        // Inexact by design: no special exact-alarm permission. Doze may delay delivery.
        context.getSystemService(AlarmManager::class.java).setAndAllowWhileIdle(
            AlarmManager.RTC_WAKEUP, next.toInstant().toEpochMilli(), pending(context))
    }
    fun disable(context: Context) {
        prefs(context).edit().putBoolean("reminder", false).apply()
        context.getSystemService(AlarmManager::class.java).cancel(pending(context))
        context.getSystemService(NotificationManager::class.java).cancel(20)
    }
    fun receive(context: Context, action: String?) {
        if (!enabled(context)) return
        if (action == ACTION && permitted(context)) {
            val open = PendingIntent.getActivity(context, 0, Intent(context, MainActivity::class.java),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val notification = Notification.Builder(context, CHANNEL).setSmallIcon(R.drawable.ic_notification)
                .setContentTitle("Give a friend a little boost 🔥")
                .setContentText("Your daily GAS polls are waiting.").setAutoCancel(true).setContentIntent(open).build()
            context.getSystemService(NotificationManager::class.java).notify(20, notification)
        }
        schedule(context)
    }
}

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) = DailyReminder.receive(context, intent.action)
}
