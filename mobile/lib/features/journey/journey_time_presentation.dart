import 'dart:async';

import 'package:flutter/material.dart';
import 'package:timezone/data/latest.dart' as timezone_data;
import 'package:timezone/timezone.dart' as tz;

/// Calendar presentation only: it never decides Journey or Jour J capabilities.
/// The owner provides a civil occurrence date (YYYY-MM-DD). We compare civil
/// calendar dates, not elapsed 24-hour intervals (DST-safe day counts).
class JourneyDayPresentation {
  const JourneyDayPresentation._();

  static bool _timezonesReady = false;

  static DateTime? _currentCalendarDate(DateTime now, String? timezoneName) {
    if (timezoneName == null || timezoneName.isEmpty) return now.toLocal();
    try {
      if (!_timezonesReady) {
        timezone_data.initializeTimeZones();
        _timezonesReady = true;
      }
      return tz.TZDateTime.from(now.toUtc(), tz.getLocation(timezoneName));
    } on Exception {
      // No marker is safer than a marker in an unknown timezone.
      return null;
    }
  }

  /// The event's midnight may occur at a different time from the device's.
  static Duration nextMidnightDelay(DateTime now, {String? timezoneName}) {
    final calendarNow = _currentCalendarDate(now, timezoneName);
    if (calendarNow == null) return const Duration(hours: 1);
    DateTime next;
    if (timezoneName != null && timezoneName.isNotEmpty) {
      final zone = tz.getLocation(timezoneName);
      next = tz.TZDateTime(
        zone,
        calendarNow.year,
        calendarNow.month,
        calendarNow.day + 1,
      );
    } else {
      next = DateTime(calendarNow.year, calendarNow.month, calendarNow.day + 1);
    }
    final delay = next.difference(now);
    return delay.isNegative ? const Duration(seconds: 1) : delay;
  }

  static DateTime? civilDate(String? value) {
    if (value == null || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) {
      return null;
    }
    final year = int.tryParse(value.substring(0, 4));
    final month = int.tryParse(value.substring(5, 7));
    final day = int.tryParse(value.substring(8, 10));
    if (year == null || month == null || day == null) return null;
    final date = DateTime.utc(year, month, day);
    if (date.year != year || date.month != month || date.day != day) {
      return null;
    }
    return date;
  }

  /// Compare calendar days in the Occurrence's own IANA timezone. All
  /// timezone rules are bundled on-device: never a network dependency.
  static int? dayOffset(
    String? occurrenceDate,
    DateTime now, {
    String? timezoneName,
  }) {
    final date = civilDate(occurrenceDate);
    if (date == null) return null;
    final today = _currentCalendarDate(now, timezoneName);
    if (today == null) return null;
    final civilToday = DateTime.utc(today.year, today.month, today.day);
    return civilToday.difference(date).inDays;
  }

  static String? badge(
    String? occurrenceDate,
    DateTime now, {
    String? timezoneName,
  }) {
    final offset = dayOffset(occurrenceDate, now, timezoneName: timezoneName);
    if (offset == null) return null;
    if (offset == 0) return 'Jour J';
    return offset < 0 ? 'Jour −${-offset}' : 'Jour J +$offset';
  }

  static String? clock(String? time) {
    if (time == null) return null;
    final match = RegExp(r'^(\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$')
        .firstMatch(time);
    if (match == null) return null;
    final hour = int.tryParse(match.group(1)!);
    final minute = int.tryParse(match.group(2)!);
    if (hour == null || hour > 23 || minute == null || minute > 59) {
      return null;
    }
    return '${hour.toString().padLeft(2, '0')}h${minute.toString().padLeft(2, '0')}';
  }

  static String? place({String? name, String? locality}) {
    final primary = name?.trim();
    if (primary != null && primary.isNotEmpty) return primary;
    final fallback = locality?.trim();
    return fallback == null || fallback.isEmpty ? null : fallback;
  }

  static String? additionalPlace({
    String? name,
    String? locality,
    String? address,
  }) {
    final shown = place(name: name, locality: locality);
    final candidates = <String>[];
    for (final candidate in [address, locality]) {
      final value = candidate?.trim();
      if (value == null || value.isEmpty) continue;
      if (value.toLowerCase() == shown?.toLowerCase()) continue;
      if (candidates.any((old) => old.toLowerCase() == value.toLowerCase())) {
        continue;
      }
      candidates.add(value);
    }
    return candidates.isEmpty ? null : candidates.join(' · ');
  }
}

/// Lightweight civil-date badge. Re-evaluated at the next local midnight;
/// there is no API request, fake event status or perpetual polling.
class JourneyDayBadge extends StatefulWidget {
  const JourneyDayBadge({
    super.key,
    required this.occurrenceDate,
    this.timezoneName,
  });

  final String occurrenceDate;
  final String? timezoneName;

  @override
  State<JourneyDayBadge> createState() => _JourneyDayBadgeState();
}

class _JourneyDayBadgeState extends State<JourneyDayBadge> {
  Timer? _midnight;

  @override
  void initState() {
    super.initState();
    _schedule();
  }

  @override
  void didUpdateWidget(covariant JourneyDayBadge oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.occurrenceDate != widget.occurrenceDate ||
        oldWidget.timezoneName != widget.timezoneName) {
      _midnight?.cancel();
      _schedule();
    }
  }

  void _schedule() {
    final now = DateTime.now();
    _midnight = Timer(
      JourneyDayPresentation.nextMidnightDelay(
            now,
            timezoneName: widget.timezoneName,
          ) +
          const Duration(seconds: 1),
      () {
        if (!mounted) return;
        setState(() {});
        _schedule();
      },
    );
  }

  @override
  void dispose() {
    _midnight?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final offset = JourneyDayPresentation.dayOffset(
      widget.occurrenceDate,
      now,
      timezoneName: widget.timezoneName,
    );
    final label = JourneyDayPresentation.badge(
      widget.occurrenceDate,
      now,
      timezoneName: widget.timezoneName,
    );
    if (offset == null || label == null) return const SizedBox.shrink();
    final spoken = offset == 0
        ? "C'est aujourd'hui"
        : offset < 0
        ? 'Dans ${-offset} jours'
        : 'Il y a $offset jours';
    return Semantics(
      label: '$label. $spoken',
      child: ExcludeSemantics(
        child: Container(
          key: const Key('journey-relative-day'),
          decoration: BoxDecoration(
            color: const Color(0xFF5232DB),
            borderRadius: BorderRadius.circular(12),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w800,
              fontSize: 16,
            ),
          ),
        ),
      ),
    );
  }
}
