package com.makolo

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.RemoteViews
import es.antonborri.home_widget.HomeWidgetProvider

class MakoloAmbientWidgetProvider : HomeWidgetProvider() {
    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
        widgetData: android.content.SharedPreferences,
    ) {
        appWidgetIds.forEach { widgetId ->
            val views = RemoteViews(context.packageName, R.layout.makolo_ambient_widget)
            val title = widgetData.getString("makolo.title", null)
            val subtitle = widgetData.getString("makolo.subtitle", null)
            val status = widgetData.getString("makolo.status", null)
            views.setTextViewText(R.id.makolo_widget_title, title ?: "Makolo")
            views.setTextViewText(
                R.id.makolo_widget_subtitle,
                subtitle ?: status ?: "Tout est en ordre. ✓",
            )

            val deepLink = widgetData.getString("makolo.deep_link", null)
            if (!deepLink.isNullOrBlank()) {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(deepLink)).apply {
                    setPackage(context.packageName)
                }
                val pendingIntent = PendingIntent.getActivity(
                    context,
                    widgetId,
                    intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                )
                views.setOnClickPendingIntent(R.id.makolo_widget_root, pendingIntent)
            }
            appWidgetManager.updateAppWidget(widgetId, views)
        }
    }
}
