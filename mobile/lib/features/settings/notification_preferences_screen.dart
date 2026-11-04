import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';
import '../../features/interoperability/push_device_controls.dart';
import '../../data/local/profile_store.dart';
import '../../design/makolo_theme.dart';
import '../../notifications/notification_repository.dart';

/// Preferences are owned by Accounts and synchronized through Notifications.
class NotificationPreferencesScreen extends StatefulWidget {
  const NotificationPreferencesScreen({super.key, required this.repository, this.runtime});

  final NotificationRepository repository;
  final AppRuntime? runtime;

  @override
  State<NotificationPreferencesScreen> createState() =>
      _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState
    extends State<NotificationPreferencesScreen> {
  String? _error;
  bool _saving = false;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  Future<void> _refresh() async {
    if (widget.repository.sync == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.repository.refreshPreferences();
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'Actualisation indisponible. Les dernières préférences connues sont conservées.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _change(String key, Object? value) =>
      _changeMany({key: value});

  Future<void> _changeMany(Map<String, dynamic> changes) async {
    if (_saving || widget.repository.sync == null) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.repository.updatePreferences(changes);
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'La modification n’a pas été confirmée. Réessayez lorsque le réseau est disponible.',
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  TimeOfDay? _parseTime(Object? value) {
    if (value is! String) return null;
    final parts = value.split(':');
    if (parts.length < 2) return null;
    final hour = int.tryParse(parts[0]);
    final minute = int.tryParse(parts[1]);
    if (hour == null ||
        minute == null ||
        hour < 0 ||
        hour > 23 ||
        minute < 0 ||
        minute > 59)
      return null;
    return TimeOfDay(hour: hour, minute: minute);
  }

  Future<void> _chooseTime(String key, Object? current) async {
    if (_saving || widget.repository.sync == null) return;
    final picked = await showTimePicker(
      context: context,
      initialTime: _parseTime(current) ?? const TimeOfDay(hour: 22, minute: 0),
    );
    if (picked == null || !mounted) return;
    final time =
        picked.hour.toString().padLeft(2, '0') +
        ':' +
        picked.minute.toString().padLeft(2, '0');
    await _change(key, time);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: StreamBuilder<StoredProjection?>(
        stream: widget.repository.watchPreferences(),
        builder: (context, snapshot) {
          final values = snapshot.data?.payload;
          if (values == null && _loading) {
            return const Center(child: CircularProgressIndicator());
          }
          if (values == null) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Préférences non disponibles sur cet appareil.'),
                  TextButton(
                    onPressed: _refresh,
                    child: const Text('Réessayer'),
                  ),
                ],
              ),
            );
          }
          final editable = widget.repository.sync != null && !_saving;
          const recommended = [
            'push_notifications',
            'email_notifications',
            'sms_notifications',
            'security_notifications',
            'event_notifications',
            'service_notifications',
            'opportunity_notifications',
          ];
          final someDisabled = recommended.any((key) => values[key] == false);
          final quietStart = values['quiet_hours_start'];
          final quietEnd = values['quiet_hours_end'];
          Widget toggle(String key, String title, String detail) {
            return SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(title),
              subtitle: Text(detail),
              value: values[key] == true,
              onChanged: editable ? (value) => _change(key, value) : null,
            );
          }

          return ListView(
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            children: [
              if (_loading || _saving) const LinearProgressIndicator(),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    vertical: MakoloSpacing.sm,
                  ),
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (widget.repository.sync == null)
                const Text(
                  'Dernières préférences connues : modification hors ligne indisponible.',
                ),
              if (widget.runtime != null) ...[
                PushDeviceControls(
                  runtime: widget.runtime!,
                  mutationsEnabled: widget.runtime!.isAuthenticated &&
                      widget.runtime!.api != null &&
                      widget.runtime!.sync != null &&
                      !_loading &&
                      !_saving &&
                      _error == null,
                  onChanged: () async {
                    await widget.runtime!.sync?.pullInteroperability();
                  },
                ),
                const SizedBox(height: MakoloSpacing.lg),
              ],
              if (someDisabled)
                Padding(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      onPressed: editable
                          ? () => _changeMany({
                                for (final key in recommended) key: true,
                              })
                          : null,
                      icon: const Icon(Icons.notifications_active_outlined),
                      label: const Text('Activer les notifications utiles'),
                    ),
                  ),
                ),
              Text('Canaux', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: MakoloSpacing.sm),
              toggle(
                'push_notifications',
                'Sur cet appareil',
                'Avec l’autorisation du téléphone.',
              ),
              toggle(
                'email_notifications',
                'E-mail',
                'Recevoir les informations par e-mail.',
              ),
              toggle(
                'sms_notifications',
                'SMS',
                'Recevoir les informations par SMS.',
              ),
              const SizedBox(height: MakoloSpacing.lg),
              Text(
                'À propos de vos activités',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              toggle(
                'security_notifications',
                'Sécurité',
                'Connexions et protection du compte.',
              ),
              toggle(
                'event_notifications',
                'Événements',
                'Changements et rappels importants.',
              ),
              toggle(
                'service_notifications',
                'Services',
                'Suivi de vos services.',
              ),
              toggle(
                'opportunity_notifications',
                'Opportunités',
                'Évolutions de vos possibilités.',
              ),
              toggle(
                'marketing_notifications',
                'Communications commerciales',
                'Offres et messages promotionnels, à votre choix.',
              ),
              const SizedBox(height: MakoloSpacing.lg),
              Text(
                'Heures calmes',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Activer les heures calmes'),
                subtitle: const Text('Moins d’alertes pendant vos moments de repos.'),
                value: values['quiet_hours_enabled'] == true,
                onChanged: editable && quietStart != null && quietEnd != null
                    ? (value) => _change('quiet_hours_enabled', value)
                    : null,
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Début'),
                subtitle: Text(
                  _parseTime(quietStart)?.format(context) ?? 'À définir',
                ),
                trailing: const Icon(Icons.schedule_outlined),
                onTap: editable
                    ? () => _chooseTime('quiet_hours_start', quietStart)
                    : null,
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Fin'),
                subtitle: Text(
                  _parseTime(quietEnd)?.format(context) ?? 'À définir',
                ),
                trailing: const Icon(Icons.schedule_outlined),
                onTap: editable
                    ? () => _chooseTime('quiet_hours_end', quietEnd)
                    : null,
              ),
            ],
          );
        },
      ),
    );
  }
}
