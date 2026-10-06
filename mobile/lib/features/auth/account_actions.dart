import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../auth/auth_repository.dart';

enum _AccountAction { switchAccount, logout }

Future<void> endMakoloAccountSession({
  required AppRuntime runtime,
  required VoidCallback onAuthenticationChanged,
}) async {
  final profileId = runtime.session?.profileId;
  runtime.recovery.markLoggedOut();
  if (profileId != null) {
    await runtime.tokens.clearAccountSession(profileId);
  }

  final api = runtime.api;
  if (api == null) {
    await runtime.tokens.clearSession();
    onAuthenticationChanged();
    return;
  }

  if (runtime.config?.firebase.enabled == true) {
    try {
      final installationId = await runtime.tokens.deviceInstanceId();
      await api.delete(
        'api/v1/notifications/push/endpoints/',
        body: {'provider': 'fcm', 'installation_id': installationId},
      );
    } on Object {
      // Local logout remains authoritative for the device. A stale push
      // endpoint is harmless and will be reconciled on a later authenticated
      // registration.
    }
  }

  unawaited(
    AuthRepository(
      api,
      runtime.tokens,
    ).logout(onLocalSessionEnded: onAuthenticationChanged),
  );
}

class AccountActionsButton extends StatefulWidget {
  const AccountActionsButton({
    super.key,
    required this.runtime,
    required this.onAuthenticationChanged,
  });

  final AppRuntime runtime;
  final VoidCallback onAuthenticationChanged;

  @override
  State<AccountActionsButton> createState() => _AccountActionsButtonState();
}

class _AccountActionsButtonState extends State<AccountActionsButton> {
  bool _busy = false;

  Future<void> _handle(_AccountAction action) async {
    if (_busy) return;
    if (action == _AccountAction.switchAccount) {
      widget.runtime.recovery.markAccountSwitch();
      context.push('/accounts');
      return;
    }

    setState(() => _busy = true);
    await endMakoloAccountSession(
      runtime: widget.runtime,
      onAuthenticationChanged: widget.onAuthenticationChanged,
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<_AccountAction>(
      key: const Key('account-actions'),
      tooltip: 'Compte',
      enabled: !_busy,
      icon: const Icon(Icons.account_circle_outlined),
      onSelected: _handle,
      itemBuilder: (context) => const [
        PopupMenuItem(
          value: _AccountAction.switchAccount,
          child: ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.switch_account_outlined),
            title: Text('Changer de compte'),
          ),
        ),
        PopupMenuItem(
          value: _AccountAction.logout,
          child: ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.logout),
            title: Text('Se déconnecter'),
          ),
        ),
      ],
    );
  }
}
