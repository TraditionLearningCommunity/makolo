import 'dart:async';
import 'dart:io';

import '../../platform/notifications/push_permission_gateway.dart';
import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';
import '../../platform/notifications/push_endpoint_registrar.dart';
import '../../platform/notifications/push_token_source.dart';

/// Three independent post-write facts: server registration, device list
/// freshness, and the parent Z16 projection. Never collapse them to success.
String pushActivationConfirmation({
  required bool devicesRefreshed,
  required bool projectionRefreshed,
}) {
  if (!devicesRefreshed) {
    return 'Notifications activées. La liste des appareils n’a pas pu être actualisée.';
  }
  if (!projectionRefreshed) {
    return 'Notifications activées. Actualisation encore nécessaire.';
  }
  return 'Notifications activées sur cet appareil.';
}

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
  int _ownerGeneration = 0;

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
      _ownerGeneration++;
      _busy = false;
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
      if (mounted) {
        setState(() {
          _loading = false;
          _devices = const [];
          _error = 'Impossible d’afficher vos appareils.';
        });
      }
      return;
    }
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final payload = (await api.get('api/v1/notifications/push/endpoints/'))
          .jsonObject();
      final values = payload['results'];
      if (values is! List) throw const FormatException('Invalid push owner');
      final devices = <Map<String, String>>[];
      for (final value in values) {
        if (value is! Map ||
            value['id'] is! String ||
            value['platform'] is! String ||
            value['provider'] != 'fcm' ||
            value['active'] != true) {
          continue;
        }
        devices.add({
          'id': value['id'] as String,
          'platform': value['platform'] as String,
          'appVersion': value['app_version'] is String
              ? value['app_version'] as String
              : '',
          'deviceName': value['device_name'] is String
              ? value['device_name'] as String
              : '',
          'lastSeen': value['last_seen_at'] is String
              ? value['last_seen_at'] as String
              : '',
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
        _error = 'Impossible d’afficher vos appareils.';
      });
    }
  }

  Future<void> _confirmRevoke(String id) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Retirer cet appareil ?'),
        content: const Text(
          'Il ne recevra plus les alertes Makolo. '
          'Vous pourrez les réactiver depuis cet appareil.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Retirer'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) await _revoke(id);
  }

  Future<void> _revoke(String id) async {
    if (_busy || !widget.mutationsEnabled || widget.runtime.api == null) return;
    final ownerRuntime = widget.runtime;
    final version = _ownerGeneration;
    setState(() => _busy = true);
    var committed = false;
    var refreshed = false;
    try {
      await ownerRuntime.api!.delete(
        'api/v1/notifications/push/endpoints/${Uri.encodeComponent(id)}/',
      );
      committed = true;
      if (!mounted ||
          version != _ownerGeneration ||
          !identical(ownerRuntime, widget.runtime)) {
        return;
      }
      await _load();
      refreshed = _error == null;
      try {
        await widget.onChanged();
      } on Object {
        refreshed = false;
      }
      if (!mounted ||
          version != _ownerGeneration ||
          !identical(ownerRuntime, widget.runtime)) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            refreshed
                ? 'Appareil retiré.'
                : 'Appareil retiré. Impossible d’actualiser la liste.',
          ),
        ),
      );
    } on Object {
      if (mounted &&
          version == _ownerGeneration &&
          identical(ownerRuntime, widget.runtime)) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              committed
                  ? 'Appareil retiré. La liste n’a pas pu être actualisée.'
                  : 'Impossible de confirmer le retrait. Actualisez avant de réessayer.',
            ),
          ),
        );
      }
    } finally {
      if (mounted &&
          version == _ownerGeneration &&
          identical(ownerRuntime, widget.runtime)) {
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _enableHere() async {
    if (_busy || !widget.mutationsEnabled || widget.runtime.api == null) return;
    final ownerRuntime = widget.runtime;
    final version = _ownerGeneration;
    setState(() => _busy = true);
    PushEndpointRegistrar? registrar;
    try {
      if (!await PushPermissionGateway.request()) {
        throw StateError('Permission de notifications refusée.');
      }
      registrar = PushEndpointRegistrar(
        api: ownerRuntime.api!,
        tokens: ownerRuntime.tokens,
        source: FirebasePushTokenSource.system(),
      );
      await registrar.reactivateCurrent();
      if (!mounted ||
          version != _ownerGeneration ||
          !identical(ownerRuntime, widget.runtime)) {
        return;
      }
      await _load();
      final devicesRefreshed = _error == null;
      var projectionRefreshed = false;
      try {
        await widget.onChanged();
        projectionRefreshed = true;
      } on Object {
        // Registration succeeded, but the parent Z16 view was not verified.
        // Do not misrepresent that partial refresh as a full success.
      }
      if (mounted &&
          version == _ownerGeneration &&
          identical(ownerRuntime, widget.runtime)) {
        final message = pushActivationConfirmation(
          devicesRefreshed: devicesRefreshed,
          projectionRefreshed: projectionRefreshed,
        );
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(message)));
      }
    } on Object {
      if (mounted &&
          version == _ownerGeneration &&
          identical(ownerRuntime, widget.runtime)) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Impossible d’activer les alertes. Vérifiez les autorisations du téléphone.',
            ),
          ),
        );
      }
    } finally {
      registrar?.dispose();
      if (mounted &&
          version == _ownerGeneration &&
          identical(ownerRuntime, widget.runtime)) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (_loading) const LinearProgressIndicator(minHeight: 2),
        if (_error != null)
          TextButton.icon(
            onPressed: () => unawaited(_load()),
            icon: const Icon(Icons.refresh),
            label: Text(_error!),
          ),
        if (!_loading && _error == null && _devices.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text('Aucun appareil autorisé.'),
          ),
        for (final device in _devices) ...[
          Padding(
            key: Key('push-device-${device['id']}'),
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(
              children: [
                Icon(
                  device['platform'] == 'android'
                      ? Icons.smartphone_rounded
                      : Icons.phone_iphone_rounded,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  size: 24,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        device['deviceName']!.trim().isNotEmpty
                            ? device['deviceName']!.trim()
                            : device['platform'] == 'android'
                            ? 'Appareil Android'
                            : 'Appareil Apple',
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                      if (DateTime.tryParse(device['lastSeen']!) != null)
                        Text(
                          'Dernière activité · ${MaterialLocalizations.of(context).formatMediumDate(DateTime.parse(device['lastSeen']!).toLocal())}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                TextButton(
                  onPressed: _busy || !widget.mutationsEnabled
                      ? null
                      : () => unawaited(_confirmRevoke(device['id']!)),
                  child: const Text('Retirer'),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
        ],
        if (widget.runtime.config?.firebase.enabled == true &&
            (Platform.isAndroid || Platform.isIOS))
          OutlinedButton.icon(
            key: const Key('push-reactivate-current'),
            onPressed: _busy || !widget.mutationsEnabled
                ? null
                : () => unawaited(_enableHere()),
            icon: const Icon(Icons.add_alert_outlined),
            label: const Text('Autoriser cet appareil'),
          ),
        if (!widget.mutationsEnabled)
          const Text(
            'La gestion des appareils est indisponible pour le moment.',
          ),
      ],
    );
  }
}
