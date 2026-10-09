import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';
import '../../auth/auth_repository.dart';
import '../../design/makolo_theme.dart';
import '../auth/auth_error_messages.dart';

class ChangePasswordScreen extends StatefulWidget {
  const ChangePasswordScreen({
    super.key,
    required this.runtime,
    required this.onPasswordChanged,
  });

  final AppRuntime runtime;
  final VoidCallback onPasswordChanged;

  @override
  State<ChangePasswordScreen> createState() => _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends State<ChangePasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  String? _required(String? value) =>
      (value?.isEmpty ?? true) ? 'Ce champ est requis.' : null;

  String? _confirmPassword(String? value) {
    final required = _required(value);
    if (required != null) return required;
    if (value != _next.text)\n      return 'Les deux mots de passe doivent être identiques.';
    return null;
  }

  Future<void> _submit() async {
    if (_busy || !_formKey.currentState!.validate()) return;
    final api = widget.runtime.api;
    if (api == null) {
      setState(() => _error = 'Cette action est indisponible pour le moment.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AuthRepository(api, widget.runtime.tokens).changePassword(
        currentPassword: _current.text,
        newPassword: _next.text,
        newPasswordConfirm: _confirm.text,
      );
      if (!mounted) return;
      widget.onPasswordChanged();
    } on Object catch (error) {
      final message = await resolvedAuthErrorMessage(
        error,
        fallback: 'Le mot de passe n’a pas pu être modifié.',
      );
      if (mounted) setState(() => _error = message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Changer le mot de passe')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            children: [
              TextFormField(
                key: const Key('current-password'),
                controller: _current,
                obscureText: true,
                autofillHints: const [AutofillHints.password],
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(\n                  labelText: 'Mot de passe actuel',\n                ),
                validator: _required,
              ),
              const SizedBox(height: MakoloSpacing.md),
              TextFormField(
                key: const Key('new-password'),
                controller: _next,
                obscureText: true,
                autofillHints: const [AutofillHints.newPassword],
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(\n                  labelText: 'Nouveau mot de passe',\n                ),
                validator: _required,
              ),
              const SizedBox(height: MakoloSpacing.md),
              TextFormField(
                key: const Key('confirm-password'),
                controller: _confirm,
                obscureText: true,
                autofillHints: const [AutofillHints.newPassword],
                textInputAction: TextInputAction.done,
                decoration: const InputDecoration(\n                  labelText: 'Confirmer le mot de passe',\n                ),
                validator: _confirmPassword,
                onFieldSubmitted: (_) => _submit(),
              ),
              if (_error != null) ...[
                const SizedBox(height: MakoloSpacing.md),
                Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    key: const Key('change-password-error'),
                    style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                ),
              ],
              const SizedBox(height: MakoloSpacing.lg),
              FilledButton(
                key: const Key('change-password-submit'),
                onPressed: _busy ? null : _submit,
                child: Text(\n                  _busy ? 'Modification…' : 'Modifier le mot de passe',\n                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
