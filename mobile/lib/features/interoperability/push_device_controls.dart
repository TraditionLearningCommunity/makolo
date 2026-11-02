import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';

/// Online-only, owner-scoped Notifications management.
class PushDeviceControls extends StatefulWidget {
  const PushDeviceControls({
    super.key,
    required this.runtime,
    required this.mutationsEnabled,
    required this.onChanged,
  });

  final AppRuntime runtime;
  final bool mutationsEnabled;
  final Future<void> Function() onChanged;

  @override
  State<PushDeviceControls> createState() => _PushDeviceControlsState();
}

class _PushDeviceControlsState extends State<PushDeviceControls> {
  bool _loading = true;
  bool _busy = false;
  String? _error;
  List<Map<String, String>> _devices = const [];
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant PushDeviceControls oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.runtime, widget.runtime)) {
      _generation++;
      _devices = const [];
      _error = null;
      _loading = true;
      unawaited(_load());
    }
  }

  Future<void> _load() async {
    final generation = ++_generation;
    final api = widget.runtime.api;
    if (api == null) {
      if (mounted) setState(() {
        _loading = false;
        _devices = const [];
        _error = 'Service Notifications indisponible.';
      });
      return;
    }
    if (mounted) setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final payload = (await api.get(
        'api/v1/notifications/push/endpoints/',
      )).jsonObject();
      final values = payload['results'];
      if (values is! List) throw const FormatException('Invalid push owner');
      final devices = <Map<String, String>>[];
      for (final value in values) {
        if (value is! Map ||
            value['id'] is! String ||
            value['platform'] is! String ||
            value['provider'] != 'fcm' ||
            value['active'] != true) continue;
        devices.add({
          'id': value['id'] as String,
          'platform': value['platform'] as String,
          'appVersion': value['app_version'] is String
              ? value['app_version'] as String : '',
        });
      }
      if (!mounted || generation != _generation) return;
      setState(() {
        _devices = devices;
        _loading = false;
      });
    } on Object {
      if (!mounted || generation != _generation) return;
      setState(() {
        _devices = const [];
        _loading = false;
        _error = 'Impossible de vérifier les appareils de ce Profil.';
      });
    }
  }

  Future<void> _revoke(String id) async {
    if (_busy || !widget.mutationsEnabled || widget.runtime.api == null) return;
    setState(() => _busy = true);
    try {
      await widget.runtime.api!.delete(
        'api/v1/notifications/push/endpoints/${Uri.encodeComponent(id)}/',
      );
      await _load();
      try {
        await widget.onChanged();
      } on Object {
        // The owner confirmed the mutation; Z16 freshness can recover later.
      }
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Appareil retiré des notifications Makolo.'),
      ));
    } on Object {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Retrait non confirmé. Aucun succès local supposé.'),
      ));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Mes appareils de notification',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 6),
        const Text('Appareils enregistrés auprès de Notifications. '
            'Leur présence ne garantit pas la livraison de chaque message.'),
        if (_loading) const LinearProgressIndicator(minHeight: 2),
        if (_error != null)
          TextButton.icon(
            onPressed: () => unawaited(_load()),
            icon: const Icon(Icons.refresh),
            label: Text(_error!),
          ),
        if (!_loading && _error == null && _devices.isEmpty)
          const Text('Aucun appareil actif pour ce Profil.'),
        for (final device in _devices)
          Card(
            child: ListTile(
              key: Key('push-device-${device['id']}'),
              leading: const Icon(Icons.notifications_active_outlined),
              title: Text(device['platform'] == 'android' ? 'Android' : 'iOS'),
              subtitle: device['appVersion']!.isEmpty
                  ? null : Text('Makolo ${device['appVersion']}'),
              trailing: OutlinedButton(
                onPressed: _busy || !widget.mutationsEnabled
                    ? null : () => unawaited(_revoke(device['id']!)),
                child: const Text('Retirer'),
              ),
            ),
          ),
        if (!widget.mutationsEnabled)
          const Text('Gestion suspendue tant que la connexion ou les droits '
              'ne sont pas confirmés.'),
      ],
    );
  }
}
