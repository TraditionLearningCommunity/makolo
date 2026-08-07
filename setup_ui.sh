#!/bin/bash

echo "======================================="
echo "CREATION UI STRUCTURE MAKOLO"
echo "======================================="

# =========================

# DOSSIERS

# =========================

mkdir -p templates/base
mkdir -p templates/partials
mkdir -p templates/components
mkdir -p templates/accounts

echo "Dossiers créés."

# =========================

# BASE APP.HTML

# =========================

cat > templates/base/app.html << 'EOF'
{% load static %}

<!DOCTYPE html>

<html lang="fr" class="h-full bg-gray-950">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

```
<title>
    {% block title %}
        Makolo
    {% endblock %}
</title>

<!-- Tailwind -->
<link rel="stylesheet" href="{% static 'css/output.css' %}">

<!-- HTMX -->
<script src="https://unpkg.com/htmx.org@1.9.12"></script>

<!-- Alpine.js -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>

<!-- Lucide Icons -->
<script src="https://unpkg.com/lucide@latest"></script>

{% block extra_css %}{% endblock %}
```

</head>

<body class="h-full bg-gray-950 text-white">

```
<div class="min-h-screen flex">

    {% include 'partials/sidebar.html' %}

    <div class="flex-1 flex flex-col">

        {% include 'partials/navbar.html' %}

        <main class="flex-1 p-6 md:p-8 overflow-y-auto">

            {% include 'partials/messages.html' %}

            {% block content %}
            {% endblock %}

        </main>

    </div>

</div>

<script>
    lucide.createIcons();
</script>

{% block extra_js %}{% endblock %}
```

</body>
</html>
EOF

echo "app.html créé."

# =========================

# AUTH.HTML

# =========================

cat > templates/base/auth.html << 'EOF'
{% load static %}

<!DOCTYPE html>

<html lang="fr" class="h-full bg-gray-950">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

```
<title>
    {% block title %}
        Auth | Makolo
    {% endblock %}
</title>

<link rel="stylesheet" href="{% static 'css/output.css' %}">
```

</head>

<body class="min-h-screen bg-gray-950 text-white flex items-center justify-center">

```
<div class="w-full max-w-md bg-gray-900 rounded-3xl border border-gray-800 p-8 shadow-2xl">

    {% block content %}
    {% endblock %}

</div>
```

</body>
</html>
EOF

echo "auth.html créé."

# =========================

# DASHBOARD.HTML

# =========================

cat > templates/base/dashboard.html << 'EOF'
{% extends 'base/app.html' %}

{% block title %}
Dashboard | Makolo
{% endblock %}

{% block content %}

<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">

```
<div class="bg-gray-900 rounded-3xl p-6 border border-gray-800">
    <p class="text-gray-400 text-sm">
        Événements
    </p>

    <h3 class="text-4xl font-bold mt-3">
        12
    </h3>
</div>

<div class="bg-gray-900 rounded-3xl p-6 border border-gray-800">
    <p class="text-gray-400 text-sm">
        Tickets
    </p>

    <h3 class="text-4xl font-bold mt-3">
        2,431
    </h3>
</div>

<div class="bg-gray-900 rounded-3xl p-6 border border-gray-800">
    <p class="text-gray-400 text-sm">
        Revenus
    </p>

    <h3 class="text-4xl font-bold mt-3">
        \$12,400
    </h3>
</div>

<div class="bg-gray-900 rounded-3xl p-6 border border-gray-800">
    <p class="text-gray-400 text-sm">
        Scans
    </p>

    <h3 class="text-4xl font-bold mt-3">
        98%
    </h3>
</div>
```

</div>

{% endblock %}
EOF

echo "dashboard.html créé."

# =========================

# NAVBAR

# =========================

cat > templates/partials/navbar.html << 'EOF'

<header class="h-20 border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-40">

```
<div class="h-full px-6 flex items-center justify-between">

    <div>
        <h2 class="text-2xl font-semibold">
            Dashboard
        </h2>
    </div>

    <div class="flex items-center gap-4">

        <button class="w-11 h-11 rounded-2xl bg-gray-900 hover:bg-gray-800 transition flex items-center justify-center">
            <i data-lucide="bell"></i>
        </button>

        <button class="w-11 h-11 rounded-2xl bg-gray-900 hover:bg-gray-800 transition flex items-center justify-center">
            <i data-lucide="moon"></i>
        </button>

        <div class="flex items-center gap-3 bg-gray-900 px-4 py-2 rounded-2xl">

            <div class="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center font-bold">
                G
            </div>

            <div class="hidden md:block">
                <p class="text-sm font-medium">
                    Gilbert
                </p>

                <p class="text-xs text-gray-400">
                    Administrator
                </p>
            </div>

        </div>

    </div>

</div>
```

</header>
EOF

echo "navbar.html créé."

# =========================

# SIDEBAR

# =========================

cat > templates/partials/sidebar.html << 'EOF'

<aside class="hidden lg:flex lg:flex-col w-72 bg-gray-900 border-r border-gray-800">

```
<div class="h-20 flex items-center px-6 border-b border-gray-800">

    <div>
        <h1 class="text-2xl font-bold tracking-tight">
            MAKOLO
        </h1>

        <p class="text-sm text-gray-400">
            Smart Event Platform
        </p>
    </div>

</div>

<nav class="flex-1 p-4 space-y-2">

    <a href="#"
       class="flex items-center gap-3 px-4 py-3 rounded-2xl bg-indigo-600 hover:bg-indigo-500 transition">

        <i data-lucide="layout-dashboard"></i>

        <span>Dashboard</span>

    </a>

    <a href="#"
       class="flex items-center gap-3 px-4 py-3 rounded-2xl hover:bg-gray-800 transition">

        <i data-lucide="calendar-days"></i>

        <span>Événements</span>

    </a>

    <a href="#"
       class="flex items-center gap-3 px-4 py-3 rounded-2xl hover:bg-gray-800 transition">

        <i data-lucide="ticket"></i>

        <span>Tickets</span>

    </a>

</nav>
```

</aside>
EOF

echo "sidebar.html créé."

# =========================

# MESSAGES

# =========================

cat > templates/partials/messages.html << 'EOF'
{% if messages %} <div class="mb-6 space-y-3">

```
    {% for message in messages %}

        <div class="rounded-2xl px-5 py-4 bg-indigo-600 text-white shadow-lg">
            {{ message }}
        </div>

    {% endfor %}

</div>
```

{% endif %}
EOF

echo "messages.html créé."

# =========================

# FOOTER

# =========================

cat > templates/partials/footer.html << 'EOF'

<footer class="border-t border-gray-800 py-6 px-6 text-center text-sm text-gray-500">
    © 2026 MAKOLO — Smart Event Platform
</footer>
EOF

echo "footer.html créé."

echo "======================================="
echo "STRUCTURE UI MAKOLO TERMINEE"
echo "======================================="
