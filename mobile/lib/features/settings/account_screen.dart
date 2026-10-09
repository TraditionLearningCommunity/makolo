import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';
import '../../auth/token_store.dart';
import '../../design/makolo_theme.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({
    super.key,
    required this.runtime,
    required this.onChangePassword,
    required this.onRememberedAccounts,
    required this.onConnections,
    required this.onBilling,
  });

  final AppRuntime runtime;
  final VoidCallback onChangePassword;
  final VoidCallback onRememberedAccounts;
  final VoidCallback onConnections;
  final VoidCallback onBilling;

  Future<DeviceAccount?> _currentAccount() async {
    final profileId = runtime.session?.profileId;
    if (profileId == null) return null;
    final accounts = await runtime.tokens.listAccounts();
    for (final account in accounts) {
      if (account.profileId == profileId) return account;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Compte')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(
          MakoloSpacing.inner,
          MakoloSpacing.md,
          MakoloSpacing.inner,
          MakoloSpacing.xl,
        ),
        children: [
          Text(
            'Accès au compte',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          FutureBuilder<DeviceAccount?>(
            future: _currentAccount(),
            builder: (context, snapshot) {
              final account = snapshot.data;
              if (account == null) {
                return const ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.person_outline),
                  title: Text('Compte Makolo'),
                );
              }
              return ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.person_outline),
                title: Text(account.publicIdentifier),
                subtitle: account.email == null ? null : Text(account.email!),
              );
            },
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.key_outlined),
            title: const Text('Changer le mot de passe'),
            trailing: const Icon(Icons.chevron_right),
            onTap: onChangePassword,
          ),
          const Divider(),
          Text('Appareil', style: Theme.of(context).textTheme.titleMedium),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.devices_outlined),
            title: const Text('Comptes mémorisés'),
            subtitle: const Text('Faciliter l’accès sur cet appareil.'),
            trailing: const Icon(Icons.chevron_right),
            onTap: onRememberedAccounts,
          ),
          const Divider(),
          Text(
            'Compte personnel',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.link_outlined),
            title: const Text('Connexions'),
            trailing: const Icon(Icons.chevron_right),
            onTap: onConnections,
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.credit_card_outlined),
            title: const Text('Abonnement & facturation'),
            trailing: const Icon(Icons.chevron_right),
            onTap: onBilling,
          ),
        ],
      ),
    );
  }
}
