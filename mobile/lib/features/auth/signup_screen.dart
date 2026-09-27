import 'package:flutter/material.dart';

import '../../app/providers.dart';
import '../../auth/auth_repository.dart';
import '../../design/makolo_theme.dart';
import 'auth_entry_frame.dart';
import 'auth_error_messages.dart';

class SignupScreen extends StatefulWidget {
  const SignupScreen({
    super.key,
    required this.runtime,
    required this.onBackToLogin,
    required this.onRegistered,
  });

  final AppRuntime runtime;
  final ValueChanged<String> onBackToLogin;
  final ValueChanged<String> onRegistered;

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final _email = TextEditingController();
  final _username = TextEditingController();
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _phone = TextEditingController();
  final _password = TextEditingController();
  final _passwordConfirm = TextEditingController();

  final _usernameFocus = FocusNode();
  final _firstNameFocus = FocusNode();
  final _lastNameFocus = FocusNode();
  final _phoneFocus = FocusNode();
  final _passwordFocus = FocusNode();
  final _passwordConfirmFocus = FocusNode();

  bool _busy = false;
  bool _showPassword = false;
  bool _showPasswordConfirm = false;
  String? _error;

  @override
  void dispose() {
    for (final controller in [
      _email,
      _username,
      _firstName,
      _lastName,
      _phone,
      _password,
      _passwordConfirm,
    ]) {
      controller.dispose();
    }
    for (final focus in [
      _usernameFocus,
      _firstNameFocus,
      _lastNameFocus,
      _phoneFocus,
      _passwordFocus,
      _passwordConfirmFocus,
    ]) {
      focus.dispose();
    }
    super.dispose();
  }

  String? _validate() {
    if (_email.text.trim().isEmpty || !_email.text.contains('@')) {
      return 'Indiquez une adresse e-mail valide.';
    }
    if (_username.text.trim().isEmpty) {
      return 'Choisissez un nom d’utilisateur.';
    }
    if (_password.text.length < 8) {
      return 'Utilisez au moins 8 caractères pour le mot de passe.';
    }
    if (_password.text != _passwordConfirm.text) {
      return 'Les deux mots de passe doivent être identiques.';
    }
    return null;
  }

  Future<void> _submit() async {
    if (_busy) return;
    final localError = _validate();
    if (localError != null) {
      setState(() => _error = localError);
      return;
    }

    final api = widget.runtime.api;
    if (api == null) {
      setState(() {
        _error = 'La création de compte est indisponible sur cette installation pour le moment.';
      });
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AuthRepository(api, widget.runtime.tokens).register(
        email: _email.text.trim(),
        username: _username.text.trim(),
        password: _password.text,
        passwordConfirm: _passwordConfirm.text,
        firstName: _firstName.text.trim(),
        lastName: _lastName.text.trim(),
        phone: _phone.text.trim(),
      );
      if (!mounted) return;
      widget.onRegistered(_email.text.trim());
    } on Object catch (error) {
      if (!mounted) return;
      setState(() => _error = signupErrorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthEntryFrame(
      title: 'Créer un compte',
      subtitle: 'Quelques informations suffisent pour préparer votre accès à Makolo.',
      onBack: () => widget.onBackToLogin(_email.text.trim()),
      child: AutofillGroup(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Votre accès',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: MakoloSpacing.md),
            TextField(
              key: const Key('signup-email'),
              controller: _email,
              enabled: !_busy,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              textInputAction: TextInputAction.next,
              onEditingComplete: () => _usernameFocus.requestFocus(),
              decoration: const InputDecoration(
                labelText: 'Adresse e-mail',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            TextField(
              key: const Key('signup-username'),
              controller: _username,
              focusNode: _usernameFocus,
              enabled: !_busy,
              autofillHints: const [AutofillHints.username],
              textInputAction: TextInputAction.next,
              onEditingComplete: () => _firstNameFocus.requestFocus(),
              decoration: const InputDecoration(
                labelText: 'Nom d’utilisateur',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: MakoloSpacing.lg),
            Text(
              'Votre nom',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: MakoloSpacing.md),
            TextField(
              controller: _firstName,
              focusNode: _firstNameFocus,
              enabled: !_busy,
              autofillHints: const [AutofillHints.givenName],
              textInputAction: TextInputAction.next,
              onEditingComplete: () => _lastNameFocus.requestFocus(),
              decoration: const InputDecoration(
                labelText: 'Prénom (facultatif)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            TextField(
              controller: _lastName,
              focusNode: _lastNameFocus,
              enabled: !_busy,
              autofillHints: const [AutofillHints.familyName],
              textInputAction: TextInputAction.next,
              onEditingComplete: () => _phoneFocus.requestFocus(),
              decoration: const InputDecoration(
                labelText: 'Nom (facultatif)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            TextField(
              controller: _phone,
              focusNode: _phoneFocus,
              enabled: !_busy,
              keyboardType: TextInputType.phone,
              autofillHints: const [AutofillHints.telephoneNumber],
              textInputAction: TextInputAction.next,
              onEditingComplete: () => _passwordFocus.requestFocus(),
              decoration: const InputDecoration(
                labelText: 'Téléphone (facultatif)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: MakoloSpacing.lg),
            Text(
              'Sécurité',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              'Utilisez au moins 8 caractères et évitez un mot de passe courant ou trop proche de vos informations personnelles.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: MakoloSpacing.md),
            TextField(
              key: const Key('signup-password'),
              controller: _password,
              focusNode: _passwordFocus,
              enabled: !_busy,
              obscureText: !_showPassword,
              autofillHints: const [AutofillHints.newPassword],
              textInputAction: TextInputAction.next,
              onEditingComplete: () => _passwordConfirmFocus.requestFocus(),
              decoration: InputDecoration(
                labelText: 'Mot de passe',
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  tooltip: _showPassword
                      ? 'Masquer le mot de passe'
                      : 'Afficher le mot de passe',
                  onPressed: _busy
                      ? null
                      : () => setState(() => _showPassword = !_showPassword),
                  icon: Icon(
                    _showPassword ? Icons.visibility_off : Icons.visibility,
                  ),
                ),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            TextField(
              key: const Key('signup-password-confirm'),
              controller: _passwordConfirm,
              focusNode: _passwordConfirmFocus,
              enabled: !_busy,
              obscureText: !_showPasswordConfirm,
              autofillHints: const [AutofillHints.newPassword],
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _submit(),
              decoration: InputDecoration(
                labelText: 'Confirmer le mot de passe',
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  tooltip: _showPasswordConfirm
                      ? 'Masquer la confirmation'
                      : 'Afficher la confirmation',
                  onPressed: _busy
                      ? null
                      : () => setState(
                          () => _showPasswordConfirm = !_showPasswordConfirm,
                        ),
                  icon: Icon(
                    _showPasswordConfirm
                        ? Icons.visibility_off
                        : Icons.visibility,
                  ),
                ),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: MakoloSpacing.md),
              Semantics(
                liveRegion: true,
                child: Text(
                  _error!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ),
            ],
            const SizedBox(height: MakoloSpacing.lg),
            FilledButton(
              key: const Key('signup-submit'),
              onPressed: _busy ? null : _submit,
              child: Text(_busy ? 'Création…' : 'Créer mon compte'),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            TextButton(
              onPressed: _busy
                  ? null
                  : () => widget.onBackToLogin(_email.text.trim()),
              child: const Text('J’ai déjà un compte'),
            ),
          ],
        ),
      ),
    );
  }
}
