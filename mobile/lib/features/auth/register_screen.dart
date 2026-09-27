import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _email = TextEditingController();
  final _username = TextEditingController();
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _password = TextEditingController();
  final _passwordConfirm = TextEditingController();

  bool _busy = false;
  bool _created = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _username.dispose();
    _firstName.dispose();
    _lastName.dispose();
    _password.dispose();
    _passwordConfirm.dispose();
    super.dispose();
  }

  Future<void> _register() async {
    final api = widget.runtime.api;
    if (api == null) return;

    if (_password.text != _passwordConfirm.text) {
      setState(
        () => _error = 'Les deux mots de passe doivent être identiques.',
      );
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await api.register(
        email: _email.text.trim(),
        username: _username.text.trim(),
        password: _password.text,
        passwordConfirm: _passwordConfirm.text,
        firstName: _firstName.text.trim(),
        lastName: _lastName.text.trim(),
      );
      if (!mounted) return;
      setState(() => _created = true);
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      setState(() => _error = _messageFor(error));
    } on Object {
      if (!mounted) return;
      setState(
        () => _error = 'Création de compte impossible pour le moment. Votre saisie reste disponible.',
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _messageFor(MakoloApiError error) {
    for (final value in error.fields.values) {
      if (value is List && value.isNotEmpty) {
        return value.first.toString();
      }
      if (value is String && value.isNotEmpty) {
        return value;
      }
    }
    return error.message;
  }

  @override
  Widget build(BuildContext context) {
    if (_created) {
      return Scaffold(
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(MakoloSpacing.xl),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Center(child: MakoloMark(size: 72)),
                    const SizedBox(height: MakoloSpacing.lg),
                    Semantics(
                      liveRegion: true,
                      child: Text(
                        'Votre compte est créé.',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    const Text(
                      'Connectez-vous pour retrouver votre activité personnelle.',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: MakoloSpacing.xl),
                    FilledButton(
                      onPressed: () => context.go('/login'),
                      child: const Text('Se connecter'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Créer un compte')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(MakoloSpacing.xl),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: widget.runtime.apiConfigured
                  ? AutofillGroup(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          TextField(
                            controller: _email,
                            keyboardType: TextInputType.emailAddress,
                            autofillHints: const [AutofillHints.email],
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Adresse e-mail',
                              border: OutlineInputBorder(),
                            ),
                          ),
                          const SizedBox(height: MakoloSpacing.md),
                          TextField(
                            controller: _username,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Identifiant',
                              border: OutlineInputBorder(),
                            ),
                          ),
                          const SizedBox(height: MakoloSpacing.md),
                          TextField(
                            controller: _firstName,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Prénom',
                              border: OutlineInputBorder(),
                            ),
                          ),
                          const SizedBox(height: MakoloSpacing.md),
                          TextField(
                            controller: _lastName,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Nom',
                              border: OutlineInputBorder(),
                            ),
                          ),
                          const SizedBox(height: MakoloSpacing.md),
                          TextField(
                            controller: _password,
                            obscureText: true,
                            autofillHints: const [AutofillHints.newPassword],
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Mot de passe',
                              border: OutlineInputBorder(),
                            ),
                          ),
                          const SizedBox(height: MakoloSpacing.md),
                          TextField(
                            controller: _passwordConfirm,
                            obscureText: true,
                            autofillHints: const [AutofillHints.newPassword],
                            onSubmitted: (_) => _busy ? null : _register(),
                            decoration: const InputDecoration(
                              labelText: 'Confirmer le mot de passe',
                              border: OutlineInputBorder(),
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
                            onPressed: _busy ? null : _register,
                            child: Text(
                              _busy ? 'Création…' : 'Créer mon compte',
                            ),
                          ),
                          const SizedBox(height: MakoloSpacing.sm),
                          TextButton(
                            onPressed: () => context.go('/discover'),
                            child: const Text('Continuer sans compte'),
                          ),
                        ],
                      ),
                    )
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text(
                          'La création de compte n’est pas disponible dans cet environnement.',
                        ),
                        const SizedBox(height: MakoloSpacing.lg),
                        TextButton(
                          onPressed: () => context.go('/discover'),
                          child: const Text('Continuer sans compte'),
                        ),
                      ],
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
