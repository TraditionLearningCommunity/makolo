import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../repositories/interoperability_repository.dart';
import 'interoperability_presentation.dart';

/// N3 owner-backed depth. Provider data is supplied by the owner catalogue;
/// credentials exist only in this transient form and in the owner POST.
class ConnectionDetailScreen extends StatefulWidget {
  const ConnectionDetailScreen.offer({
    super.key,
    required Map<String, dynamic> this.offer,
    required this.onConnect,
    this.mutationsEnabled = true,
  }) : connection = null,
       onManage = null;

  const ConnectionDetailScreen.connected({
    super.key,
    required InteroperabilityConnectionProjection this.connection,
    required this.onManage,
    this.mutationsEnabled = true,
  }) : offer = null,
       onConnect = null;

  final bool mutationsEnabled;
  final Map<String, dynamic>? offer;
  final InteroperabilityConnectionProjection? connection;
  final Future<bool> Function(Map<String, dynamic>)? onConnect;
  final Future<bool> Function(String action, String? secret)? onManage;

  @override
  State<ConnectionDetailScreen> createState() => _ConnectionDetailScreenState();
}

class _ConnectionDetailScreenState extends State<ConnectionDetailScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  final _model = TextEditingController();
  final _secret = TextEditingController();
  bool _consent = false;
  bool _busy = false;
  bool _rotating = false;
  String? _error;

  bool get _isOffer => widget.offer != null;
  bool get _canConnect =>
      widget.offer?['can_connect'] == true && widget.mutationsEnabled;
  bool get _canManage =>
      widget.connection?.manageable == true &&
      widget.connection?.owner == 'intelligence' &&
      widget.mutationsEnabled;
  String get _title => _isOffer
      ? (widget.offer?['label'] as String? ?? 'Service')
      : (widget.connection?.displayName ?? 'Connexion');

  List<String> get _capabilities {
    final Object? raw;
    if (_isOffer) {
      raw = widget.offer?['capabilities'];
    } else {
      raw = widget.connection?.capabilities;
    }
    if (raw is! List) return const [];
    return raw.whereType<String>().map(connectionCapabilityLabel).toList();
  }

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: _title);
  }

  @override
  void dispose() {
    _name.dispose();
    _model.dispose();
    _secret.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    if (!_canConnect ||
        _busy ||
        !_consent ||
        _formKey.currentState?.validate() != true) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    var confirmed = false;
    try {
      confirmed = await widget.onConnect!({
        'name': _name.text.trim(),
        'model': _model.text.trim(),
        'api_key': _secret.text.trim(),
      });
    } on Object {
      // Owner error is displayed without reflecting secrets.
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (!confirmed) _error = 'La connexion n’a pas été confirmée.';
    });
    if (confirmed) Navigator.of(context).pop();
  }

  Future<void> _manage(String action) async {
    if (_busy || !_canManage) return;
    if (action == 'rotate' && (_formKey.currentState?.validate() != true)) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    var confirmed = false;
    try {
      confirmed = await widget.onManage!(
        action,
        action == 'rotate' ? _secret.text.trim() : null,
      );
    } on Object {
      // Owner remains the authority for each mutation.
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (!confirmed) _error = 'La modification n’a pas été confirmée.';
    });
    if (confirmed) Navigator.of(context).pop();
  }

  Future<void> _remove() async {
    final accepted = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Retirer cette connexion ?'),
        content: const Text(
          'Makolo supprimera la connexion et sa clé conservée. '
          'La clé externe devra être révoquée séparément chez son fournisseur.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Retirer'),
          ),
        ],
      ),
    );
    if (accepted == true && mounted) await _manage('disconnect');
  }

  Widget _intro(BuildContext context) {
    final description = widget.offer?['description'] as String? ?? '';
    final status = widget.connection == null
        ? null
        : connectionStatusLabel(widget.connection!);
    final capabilities = _capabilities;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 64,
          height: 64,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primaryContainer,
            borderRadius: BorderRadius.circular(18),
          ),
          child: Icon(
            _isOffer ? Icons.extension_outlined : Icons.link_outlined,
            size: 30,
            color: Theme.of(context).colorScheme.onPrimaryContainer,
          ),
        ),
        const SizedBox(height: 20),
        Text(_title, style: Theme.of(context).textTheme.headlineSmall),
        if (description.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(description, style: Theme.of(context).textTheme.bodyLarge),
        ],
        if (status != null) ...[
          const SizedBox(height: 8),
          Text(status, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 4),
          Text(
            connectionExperienceMessage(widget.connection!),
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
        if (capabilities.isNotEmpty) ...[
          const SizedBox(height: 24),
          Text(
            'Ce que ce service permet',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final capability in capabilities)
                Chip(label: Text(capability)),
            ],
          ),
        ],
      ],
    );
  }

  Widget _connectForm(BuildContext context) {
    if (!_canConnect) {
      return Padding(
        padding: const EdgeInsets.only(top: 24),
        child: Text(
          'Ce service reste consultable. Pour le relier, '
          'une connexion au serveur et une configuration autorisée sont nécessaires.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );
    }
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 28),
          Text(
            'Relier ce service',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _name,
            maxLength: 120,
            decoration: const InputDecoration(
              labelText: 'Nom de la connexion',
              border: OutlineInputBorder(),
            ),
            validator: (value) => (value == null || value.trim().isEmpty)
                ? 'Indiquez un nom.'
                : null,
          ),
          if (widget.offer?['requires_model'] == true) ...[
            const SizedBox(height: 12),
            TextFormField(
              controller: _model,
              maxLength: 160,
              decoration: const InputDecoration(
                labelText: 'Identifiant du modèle',
                border: OutlineInputBorder(),
              ),
              validator: (value) => (value == null || value.trim().isEmpty)
                  ? 'Ce fournisseur requiert un modèle.'
                  : null,
            ),
          ],
          const SizedBox(height: 12),
          TextFormField(
            controller: _secret,
            obscureText: true,
            enableSuggestions: false,
            autocorrect: false,
            maxLength: 4096,
            decoration: const InputDecoration(
              labelText: 'Clé API',
              border: OutlineInputBorder(),
            ),
            validator: (value) => (value == null || value.trim().isEmpty)
                ? 'Saisissez votre clé API.'
                : null,
          ),
          const SizedBox(height: 8),
          Text(
            'La clé est conservée chiffrée côté serveur. '
            'Le fournisseur peut appliquer ses propres frais et quotas.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            value: _consent,
            onChanged: _busy
                ? null
                : (value) => setState(() => _consent = value == true),
            title: const Text(
              'J’autorise Makolo à utiliser cette clé pour les capacités indiquées.',
            ),
          ),
        ],
      ),
    );
  }

  Widget _manageActions(BuildContext context) {
    if (!_canManage) {
      return Padding(
        padding: const EdgeInsets.only(top: 24),
        child: Text(
          widget.connection?.manageable == true &&
                  widget.connection?.owner == 'intelligence'
              ? 'Gestion suspendue : vérifiez la connexion au serveur.'
              : 'Aucune gestion directe disponible dans ce contexte.',
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (widget.connection!.owner == 'intelligence' &&
            widget.connection!.enabled &&
            widget.connection!.usable &&
            widget.connection!.capabilities.any(
              (cap) => cap == 'web_research' || cap == 'structured_generate',
            )) ...[
          const SizedBox(height: 24),
          OutlinedButton.icon(
            key: Key('discover-from-connection-${widget.connection!.id}'),
            onPressed: () => context.push('/discover'),
            icon: const Icon(Icons.explore_outlined),
            label: const Text('Explorer dans Découvrir'),
          ),
        ],
        const SizedBox(height: 28),
        Text(
          'Gérer la connexion',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 12),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(
            widget.connection!.enabled
                ? Icons.pause_circle_outline
                : Icons.play_circle_outline,
          ),
          title: Text(widget.connection!.enabled ? 'Désactiver' : 'Réactiver'),
          subtitle: const Text('Le serveur vérifie votre autorité.'),
          enabled: !_busy,
          onTap: () =>
              _manage(widget.connection!.enabled ? 'disable' : 'enable'),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.key_outlined),
          title: const Text('Remplacer la clé API'),
          trailing: Icon(_rotating ? Icons.expand_less : Icons.chevron_right),
          enabled: !_busy,
          onTap: () => setState(() => _rotating = !_rotating),
        ),
        if (_rotating)
          Form(
            key: _formKey,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TextFormField(
                    controller: _secret,
                    obscureText: true,
                    autocorrect: false,
                    enableSuggestions: false,
                    maxLength: 4096,
                    decoration: const InputDecoration(
                      labelText: 'Nouvelle clé API',
                      border: OutlineInputBorder(),
                    ),
                    validator: (value) => value == null || value.trim().isEmpty
                        ? 'Saisissez la nouvelle clé.'
                        : null,
                  ),
                  FilledButton(
                    onPressed: _busy ? null : () => _manage('rotate'),
                    child: const Text('Enregistrer la nouvelle clé'),
                  ),
                ],
              ),
            ),
          ),
        const Divider(),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(
            Icons.link_off,
            color: Theme.of(context).colorScheme.error,
          ),
          title: const Text('Retirer de Makolo'),
          subtitle: const Text(
            'Supprime la relation et la clé conservée par Makolo.',
          ),
          enabled: !_busy,
          onTap: _remove,
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_isOffer ? 'Service' : 'Connexion')),
      key: const Key('connection-n3'),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
        children: [
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 600),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _intro(context),
                  if (_isOffer)
                    _connectForm(context)
                  else
                    _manageActions(context),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: _isOffer && _canConnect
          ? SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
                child: FilledButton(
                  onPressed: _busy || !_consent ? null : _connect,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Text(_busy ? 'Connexion en cours…' : 'Connecter'),
                  ),
                ),
              ),
            )
          : null,
    );
  }
}
