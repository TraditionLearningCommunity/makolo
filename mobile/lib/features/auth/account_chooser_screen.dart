import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';
import '../../app/runtime/actor_context_controller.dart';
import '../../auth/token_store.dart';
import '../../design/makolo_theme.dart';
import '../access/access_credential_vault.dart';
import 'auth_entry_frame.dart';

class DeviceAccountsScreen extends ConsumerStatefulWidget {
  const DeviceAccountsScreen({
    super.key,
    required this.runtime,
    required this.onUsePassword,
    required this.onAddAccount,
    this.onClose,
  });

  final AppRuntime runtime;
  final ValueChanged<String> onUsePassword;
  final VoidCallback onAddAccount;
  final VoidCallback? onClose;

  @override
  ConsumerState<DeviceAccountsScreen> createState() =>
      _DeviceAccountsScreenState();
}

class _DeviceAccountsScreenState extends ConsumerState<DeviceAccountsScreen> {
  late Future<List<DeviceAccount>> _accounts = widget.runtime.tokens
      .listAccounts();
  String? _busyProfileId;

  void _reload() {
    setState(() {
      _accounts = widget.runtime.tokens.listAccounts();
    });
  }

  Future<void> _activate(DeviceAccount account) async {
    if (_busyProfileId != null) return;
    if (!account.hasQuickAccess) {
      widget.onUsePassword(account.loginIdentifier);
      return;
    }
    setState(() => _busyProfileId = account.profileId);
    try {
      await widget.runtime.tokens.activateAccount(account.profileId);
      widget.runtime.recovery.markLoggedOut();
      ref.invalidate(appRuntimeProvider);
    } on Object {
      if (!mounted) return;
      widget.onUsePassword(account.loginIdentifier);
    } finally {
      if (mounted) setState(() => _busyProfileId = null);
    }
  }

  Future<void> _remove(DeviceAccount account) async {
    final remove = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Retirer ce compte de cet appareil ?'),
        content: Text(
          'Le compte ${account.publicIdentifier} restera un compte Makolo. Seuls son accès rapide et sa présence dans cette liste seront retirés de cet appareil.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Retirer'),
          ),
        ],
      ),
    );
    if (remove != true) return;
    final wasActive = widget.runtime.session?.profileId == account.profileId;
    // Removing a device account must also revoke its locally retained
    // presentation secrets. Removing a session alone need not erase the
    // Profile's durable nonsecret local-first history.
    try {
      await SecureAccessCredentialVault().clearProfile(account.profileId);
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Impossible de retirer les justificatifs protégés '
              'de cet appareil. Réessayez.',
            ),
          ),
        );
      }
      return;
    }
    await widget.runtime.tokens.removeAccount(account.profileId);
    final actorContextStore = widget.runtime.launchPreferences;
    if (actorContextStore is ActorContextStore) {
      await (actorContextStore as ActorContextStore).removeActorContext(
        account.profileId,
      );
    }
    if (wasActive) {
      widget.runtime.recovery.markLoggedOut();
      ref.invalidate(appRuntimeProvider);
      return;
    }
    _reload();
  }

  @override
  Widget build(BuildContext context) {
    return AuthEntryFrame(
      title: 'Choisir un compte',
      subtitle: 'Sélectionnez un compte pour continuer.',
      compactIdentity: true,
      footer: '',
      onClose: widget.onClose,
      child: FutureBuilder<List<DeviceAccount>>(
        future: _accounts,
        builder: (context, snapshot) {
          final accounts = snapshot.data ?? const <DeviceAccount>[];
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(
              child: CircularProgressIndicator(color: Colors.white),
            );
          }
          if (accounts.isEmpty) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Aucun autre compte n’est enregistré sur cet appareil.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white.withValues(alpha: 0.86)),
                ),
                const SizedBox(height: MakoloSpacing.lg),
                FilledButton(
                  onPressed: widget.onAddAccount,
                  style: FilledButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: MakoloColors.indigo,
                    minimumSize: const Size.fromHeight(54),
                  ),
                  child: const Text('Ajouter un compte'),
                ),
              ],
            );
          }

          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ...accounts.map(
                (account) => Padding(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.compact),
                  child: Material(
                    color: Colors.white,
                    elevation: 2,
                    shadowColor: MakoloColors.deep.withValues(alpha: 0.16),
                    borderRadius: BorderRadius.circular(MakoloRadii.large),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(MakoloRadii.large),
                      onTap: _busyProfileId == null
                          ? () => _activate(account)
                          : null,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: MakoloSpacing.md,
                          vertical: MakoloSpacing.md,
                        ),
                        child: Row(
                          children: [
                            CircleAvatar(
                              radius: 24,
                              backgroundColor: const Color(0xFFEEE9FF),
                              foregroundColor: MakoloColors.indigo,
                              child: Text(
                                account.avatarLetter,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                            const SizedBox(width: MakoloSpacing.compact),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    account.displayName,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                      color: MakoloColors.ink,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  Text(
                                    account.publicIdentifier,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      color: MakoloColors.ink.withValues(
                                        alpha: 0.72,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: MakoloSpacing.xs),
                                  Text(
                                    account.hasQuickAccess
                                        ? 'Accès rapide disponible'
                                        : 'Mot de passe requis',
                                    style: const TextStyle(
                                      color: MakoloColors.indigo,
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            if (_busyProfileId == account.profileId)
                              const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2.5,
                                ),
                              )
                            else
                              PopupMenuButton<String>(
                                tooltip: 'Actions du compte',
                                onSelected: (value) {
                                  if (value == 'remove') {
                                    _remove(account);
                                  }
                                },
                                itemBuilder: (_) => const [
                                  PopupMenuItem(
                                    value: 'remove',
                                    child: Text('Retirer de cet appareil'),
                                  ),
                                ],
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.sm),
              OutlinedButton.icon(
                onPressed: widget.onAddAccount,
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: BorderSide(
                    color: Colors.white.withValues(alpha: 0.82),
                    width: 1.25,
                  ),
                  minimumSize: const Size.fromHeight(54),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(MakoloRadii.card),
                  ),
                ),
                icon: const Icon(Icons.add),
                label: const Text('Ajouter un compte'),
              ),
            ],
          );
        },
      ),
    );
  }
}
