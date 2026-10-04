import 'package:intl/intl.dart';

abstract final class MakoloHumanization {
  static String formatDay(
    DateTime value, {
    required DateTime now,
    String locale = 'fr',
  }) {
    final localValue = value.toLocal();
    final localNow = now.toLocal();
    final valueDay = DateTime(localValue.year, localValue.month, localValue.day);
    final nowDay = DateTime(localNow.year, localNow.month, localNow.day);
    final delta = valueDay.difference(nowDay).inDays;

    return switch (delta) {
      0 => 'Aujourd’hui',
      1 => 'Demain',
      -1 => 'Hier',
      _ => DateFormat.yMMMd(locale).format(localValue),
    };
  }

  static String formatShortDate(DateTime value, {String locale = 'fr'}) =>
      DateFormat.yMd(locale).format(value.toLocal());

  static String formatLongDate(DateTime value, {String locale = 'fr'}) =>
      DateFormat.yMMMMd(locale).format(value.toLocal());

  static String formatTime(DateTime value, {String locale = 'fr'}) =>
      DateFormat.Hm(locale).format(value.toLocal());

  static String formatTimeRange(
    DateTime start,
    DateTime? end, {
    String locale = 'fr',
  }) {
    final startLabel = formatTime(start, locale: locale);
    if (end == null) return startLabel;
    return '$startLabel – ${formatTime(end, locale: locale)}';
  }

  static String formatDateTime(
    DateTime value, {
    required DateTime now,
    String locale = 'fr',
  }) =>
      '${formatDay(value, now: now, locale: locale)} · '
      '${formatTime(value, locale: locale)}';

  static String formatNumber(num value, {String locale = 'fr'}) =>
      NumberFormat.decimalPattern(locale).format(value);

  static String formatPercentFraction(
    num value, {
    String locale = 'fr',
    int decimalDigits = 0,
  }) {
    final formatter = NumberFormat.percentPattern(locale)
      ..minimumFractionDigits = decimalDigits
      ..maximumFractionDigits = decimalDigits;
    return formatter.format(value);
  }

  static String plural(
    num count, {
    required String one,
    required String other,
    String locale = 'fr',
  }) =>
      Intl.plural(
        count,
        one: one,
        other: other,
        locale: locale,
        args: [count],
      );

  static String formatDuration(Duration duration, {String locale = 'fr'}) {
    final totalMinutes = duration.inMinutes.abs();
    if (totalMinutes < 60) {
      final count = totalMinutes;
      return '$count ${plural(count, one: 'minute', other: 'minutes', locale: locale)}';
    }

    final hours = totalMinutes ~/ 60;
    final minutes = totalMinutes % 60;
    final hourLabel =
        '$hours ${plural(hours, one: 'heure', other: 'heures', locale: locale)}';
    if (minutes == 0) return hourLabel;
    return '$hourLabel $minutes min';
  }

  static String formatRelative(
    DateTime value, {
    required DateTime now,
    String locale = 'fr',
  }) {
    final delta = value.toLocal().difference(now.toLocal());
    final minutes = delta.inMinutes;
    if (minutes.abs() < 1) return 'À l’instant';
    if (minutes.abs() < 60) {
      final count = minutes.abs();
      final amount =
          '$count ${plural(count, one: 'minute', other: 'minutes', locale: locale)}';
      return minutes < 0 ? 'Il y a $amount' : 'Dans $amount';
    }

    final hours = delta.inHours;
    if (hours.abs() < 24) {
      final count = hours.abs();
      final amount =
          '$count ${plural(count, one: 'heure', other: 'heures', locale: locale)}';
      return hours < 0 ? 'Il y a $amount' : 'Dans $amount';
    }

    return formatDay(value, now: now, locale: locale);
  }

  static String? humanStatus(String? raw) {
    final value = raw?.trim().toLowerCase();
    return switch (value) {
      null || '' || 'unknown' || 'exact' => null,
      'scheduled' || 'planned' => 'Prévu',
      'estimated' => 'Estimé',
      'observed' => 'Confirmé',
      'published' => 'Publié',
      'available' => 'Disponible',
      'unavailable' => 'Indisponible',
      'action_required' => 'À faire',
      'pending' => 'En attente',
      'blocked' => 'Bloqué',
      'live' => 'En cours',
      'confirmed' => 'Confirmé',
      'completed' || 'done' => 'Terminé',
      'cancelled' || 'canceled' => 'Annulé',
      _ => null,
    };
  }

  static String? presentationLabel(String? raw) {
    final text = raw?.trim();
    if (text == null || text.isEmpty) return null;
    final mapped = humanStatus(text);
    if (mapped != null) return mapped;
    if (RegExp(r'^[a-z0-9_\\-]+
    final value = raw?.trim();
    if (value == null || value.isEmpty) return null;
    final parts = value.split('/');
    final leaf = parts.last.replaceAll('_', ' ').trim();
    if (leaf.isEmpty || leaf.toUpperCase() == 'UTC') return null;
    return leaf;
  }

  static DateTime? tryParseInstant(Object? value) {
    if (value == null) return null;
    final text = value.toString().trim();
    if (text.isEmpty) return null;
    return DateTime.tryParse(text);
  }
}
).hasMatch(text)) return null;
    return text;
  }

  static String? humanTimezone(String? raw) {
    final value = raw?.trim();
    if (value == null || value.isEmpty) return null;
    final parts = value.split('/');
    final leaf = parts.last.replaceAll('_', ' ').trim();
    if (leaf.isEmpty || leaf.toUpperCase() == 'UTC') return null;
    return leaf;
  }

  static DateTime? tryParseInstant(Object? value) {
    if (value == null) return null;
    final text = value.toString().trim();
    if (text.isEmpty) return null;
    return DateTime.tryParse(text);
  }
}
