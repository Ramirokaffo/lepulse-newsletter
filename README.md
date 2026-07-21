# Le Pulse — Newsletter Accent Média

MVP scolaire de gestion de la newsletter mensuelle **Le Pulse**, développé avec Django.

## Fonctionnalités livrées — Sprint 2

- page d'accueil responsive inspirée de la charte d'Accent Média ;
- inscription avec consentement et confirmation par e-mail ;
- désinscription sécurisée par lien individuel ;
- fiches abonnés, import/export CSV, anonymisation RGPD et actions groupées ;
- segments manuels et dynamiques ;
- création et publication de newsletters avec **TinyMCE 7** ;
- archives publiques ;
- prévisualisation, test, planification, annulation et export des campagnes ;
- exclusion automatique des abonnés non actifs ;
- suivi des ouvertures et du clic sur le bouton d'action ;
- statistiques d'ouverture et de clic sur 14 jours ;
- journal d'audit et rôles Administrateur/Rédacteur ;
- nettoyage automatique du HTML TinyMCE.

## Charte graphique

L'interface reprend les codes observés sur `accentmedia.cm` :

- orange principal : `#E84E0E` ;
- anthracite : `#1E1F2F` ;
- typographies : Poppins et Ropa Sans ;
- surfaces blanches et grises, titres larges et contrastés.

## Prérequis

- Python 3.12 ou supérieur ;
- un environnement virtuel Python ;
- une connexion internet pour charger TinyMCE et les polices Google.

## Installation

1. Créer et activer un environnement virtuel.
2. Installer les dépendances avec `python -m pip install -r requirements.txt`.
3. Copier `env.example` vers un fichier de configuration local ou exporter les variables utiles.
4. Exécuter `python manage.py migrate`.
5. Créer un compte avec `python manage.py createsuperuser`.
6. Démarrer avec `python manage.py runserver`.

L'application est ensuite disponible sur `http://127.0.0.1:8000/`.

## E-mails en développement

Par défaut, Django utilise le backend console : les e-mails et liens de confirmation sont affichés dans le terminal du serveur. Aucun message réel n'est envoyé.

Pour un serveur SMTP, définir au minimum : `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` et `DEFAULT_FROM_EMAIL`.

## Déploiement Docker

1. Copier `env.example` vers `.env` sur le serveur et remplacer toutes les valeurs d'exemple.
2. Utiliser le véritable domaine HTTPS dans `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` et `SITE_URL`.
3. Lancer `docker compose pull && docker compose up -d`.
4. Vérifier avec `docker compose ps` et `docker compose logs --tail=100 lepulse`.

La base SQLite est stockée dans le volume `lepulse_data`. Les migrations et `collectstatic` sont exécutés automatiquement au démarrage. WhiteNoise sert les fichiers statiques collectés ; Nginx doit transmettre `X-Forwarded-Proto`.

Ne jamais utiliser `*` dans `DJANGO_ALLOWED_HOSTS` en production et ne jamais versionner le fichier `.env`.

## Utilisation

1. Se connecter via `/connexion/` avec un compte ayant le statut personnel.
2. Créer une newsletter dans **Newsletters** et choisir le statut publié pour l'afficher dans les archives.
3. Créer une campagne et choisir éventuellement un segment.
4. Envoyer un test, puis déclencher ou planifier la campagne.
5. Consulter les ouvertures et clics dans le détail de la campagne.

L'envoi reste synchrone. Pour traiter les campagnes arrivées à échéance, exécuter régulièrement `python manage.py send_scheduled_campaigns` avec cron ou le planificateur du serveur.

### Rôles

- **Rédacteur** : crée les newsletters et campagnes, prévisualise et envoie des tests.
- **Administrateur** : possède en plus l'accès aux abonnés, segments, envois réels, exports et journal d'audit.

## TinyMCE

TinyMCE 7 est chargé depuis jsDelivr dans le formulaire de newsletter, sous licence GPL. Les plugins activés couvrent les listes, liens, images, tableaux, aperçu et code source.

## Tests

Exécuter `python manage.py test`. Les tests couvrent aussi les rôles, l'import CSV, le RGPD, les segments dynamiques, la sécurité HTML, les statistiques et le suivi détaillé.

## Limites du MVP

- SQLite est utilisé en développement ;
- les campagnes sont envoyées sans file de tâches distribuée ;
- le suivi de clic concerne le bouton d'action principal ;
- le HTML est limité à une liste conservatrice de balises et attributs ;
- l'hébergement de production et HTTPS restent à configurer.
