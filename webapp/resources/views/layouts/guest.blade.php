<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="csrf-token" content="{{ csrf_token() }}">

        <title>{{ config('app.name', 'Laravel') }}</title>

        <!-- Fonts -->
        <link rel="preconnect" href="https://fonts.bunny.net">
        <link href="https://fonts.bunny.net/css?family=figtree:400,500,600&display=swap" rel="stylesheet" />

        <!-- Scripts -->
        @vite(['resources/css/app.css', 'resources/js/app.js'])
    </head>
    <body class="font-sans text-gray-900 antialiased">
        <div class="min-h-screen flex bg-slate-50">
            <!-- Brand panel -->
            <div class="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-gradient-to-br from-indigo-700 via-indigo-800 to-slate-900 text-white flex-col justify-between p-12 xl:p-16">
                <div class="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/5"></div>
                <div class="pointer-events-none absolute -left-16 bottom-10 h-56 w-56 rounded-full bg-white/5"></div>

                <a href="/" class="relative inline-flex items-center gap-3">
                    <span class="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/20">
                        <x-application-logo class="h-5 w-5 text-white" />
                    </span>
                    <span class="text-lg font-semibold tracking-tight">Broadnet SMS</span>
                </a>

                <div class="relative max-w-sm">
                    <h1 class="text-3xl font-semibold leading-tight">
                        Users, Sender IDs, SMPP, API &amp; HLR — all in one place.
                    </h1>
                    <p class="mt-4 text-sm leading-relaxed text-indigo-200">
                        A lightweight management console demonstrating how an SMSC account, its services, and its traffic fit together.
                    </p>

                    <ul class="mt-8 space-y-3 text-sm text-indigo-100">
                        @foreach ([
                            'Sender ID & country permissions',
                            'SMPP accounts & IP whitelisting',
                            'API credentials',
                            'HLR lookups & traffic history',
                        ] as $feature)
                            <li class="flex items-center gap-3">
                                <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/10">
                                    <svg class="h-3 w-3 text-white" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <path d="M2.5 6.25 4.75 8.5 9.5 3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                                    </svg>
                                </span>
                                {{ $feature }}
                            </li>
                        @endforeach
                    </ul>
                </div>

                <p class="relative text-xs text-indigo-300">&copy; {{ date('Y') }} Broadnet SMS</p>
            </div>

            <!-- Form panel -->
            <div class="flex flex-1 flex-col items-center justify-center px-6 py-12 sm:px-12">
                <div class="w-full max-w-sm">
                    <div class="mb-8 flex items-center justify-center gap-3 lg:hidden">
                        <span class="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600">
                            <x-application-logo class="h-5 w-5 text-white" />
                        </span>
                        <span class="text-lg font-semibold text-gray-900">Broadnet SMS</span>
                    </div>

                    {{ $slot }}
                </div>
            </div>
        </div>

        <script src="http://localhost:8010/widget.js"
                data-agent-id="7faddd79-74b5-4626-b461-16987dd7099c"></script>
    </body>
</html>
