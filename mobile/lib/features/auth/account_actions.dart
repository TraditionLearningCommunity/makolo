import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/providers.dart';
import '../../auth/auth_repository.dart';

enum _AccountAction { switchAccount, logout }

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

  Future<void> _endSession(_AccountAction action) async {
    if (_busy) return;
    setState(() => _busy = true);

    if (action == _AccountAction.switchAccount) {
      widget.runtime.recovery.markAccountSwitch();
    } else {
      widget.runtime.recovery.markLoggedOut();
    }

    final api = widget.runtime.api;
    if (api == null) {
      await widget.runtime.tokens.clearSession();
      widget.onAuthenticationChanged();
      return;
    }

    unawaited(
      AuthRepository(
        api,
        widget.runtime.tokens,
      ).logout(onLocalSessionEnded: widget.onAuthenticationChanged),
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<_AccountAction>(
      key: const Key('account-actions'),
      tooltip: 'Compte',
      enabled: !_busy,
      icon: const Icon(Icons.account_circle_outlined),
      onSelected: _endSession,
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
