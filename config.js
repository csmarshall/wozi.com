/* =============================================================================
   wozi.com — CONFIGURATION

   Everything in this file is a SETTING. Change any of it and the machine still
   works: no geometry is derived here, and nothing here is measured by the test
   suite's mesh checks.

   What is deliberately NOT here, and must not be moved here:

     MODULE, TOOTH_*, BAND_*, RIM_UNDER_BAND, MIN_MODULE, TOOTH_ROOT_MIN
       The geometry the whole train derives from. `npm test` reads these out of
       index.html and executes them, so the suite measures what actually ships
       rather than a copy. A copy is the one thing that must never exist.

     the deal bounds (TEETH_*, ANG_*, BAND_MAX, ENDS_MAX) and the layout bounds
     (LINK_SHARE, GS_MAX, CROSS_BLEED)
       These feed the geometry the suite measures. They stay in index.html with
       the maths they serve.

     CENTRE_FAMILIES
       Its `planetary` and `ravigneaux` entries call planetaryMenuFor(), which
       lives in index.html and is extracted by the suite. The data cannot leave
       the function it depends on.

   THIS FILE MUST BE PUBLISHED. The deploy names the paths it publishes — a
   whitelist — so adding a file to the repo does NOT put it on the web. config.js
   is named in .github/workflows/deploy.yml, and CI asserts it is reachable and
   parses, because index.html falls back to a link-less machine if it is missing
   and that failure would otherwise be silent.
   ============================================================================= */

window.WOZI_CONFIG = {

  /* ---------------------------------------------------------------------------
     SERVICES — what each service IS, independent of whose account it points at.
     Shared across every person.

       label  the accessible name, and the text in the hover pill
       url    where this service lives, with `{handle}` standing in for the
              account. THE SERVICE OWNS THE STEM AND THE PERSON OWNS THE HANDLE
              (#99): `github.com` used to be written once per person who had
              GitHub, with nothing keeping the spellings in step.
       path   what the wheel's band is engraved with, same substitution.
              OPTIONAL, and defaults to `{handle}` — the handle on its own,
              which is what `mail` wants and what any service without a leading
              path segment wants.

     Substitution is LITERAL: `{handle}` is replaced with the handle exactly as
     written, never percent-encoded. `mailto:{handle}` is the reason — encoding
     the '@' of an address would change bytes that are perfectly legal
     unencoded — and every handle below is already URL-safe. A handle that needs
     escaping should be written escaped.

     A service with no `url` cannot resolve on its own and every link naming it
     must carry its own `href`. That is deliberate for `mastodon`: the instance
     is part of the account, so there is no stem to share, and pretending
     otherwise would be a shared fact that is not actually shared. Neither the
     scheme nor the trailing slashes below have been tidied — normalising is a
     change to where the links POINT, and this was a change to where they are
     WRITTEN. They are at least now visible in one place to tidy.

     Adding a service is a line here, an icon at `assets/icons/<slug>.svg`, and
     an entry in BRAND and PILL_STACK. The logo half of #70 was already shared:
     the icon is fetched by slug and the colour and wordmark face are keyed by
     slug, so nothing about a mark was ever per-person.
     --------------------------------------------------------------------------- */
  SERVICES: {
    linkedin:  { label: 'LinkedIn',  url: 'http://www.linkedin.com/in/{handle}',    path: '/in/{handle}' },
    github:    { label: 'GitHub',    url: 'https://github.com/{handle}/',           path: '/{handle}' },
    mastodon:  { label: 'Mastodon',  path: '/@{handle}' },  /* no stem: see above */
    instagram: { label: 'Instagram', url: 'http://www.instagram.com/{handle}/',     path: '/{handle}' },
    threads:   { label: 'Threads',   url: 'https://www.threads.com/{handle}',       path: '/{handle}' },
    bluesky:   { label: 'Bluesky',   url: 'https://bsky.app/profile/{handle}',      path: '/{handle}' },
    mail:      { label: 'Mail',      url: 'mailto:{handle}' },
    reddit:    { label: 'Reddit',    url: 'https://www.reddit.com/user/{handle}/',  path: '/user/{handle}' }
  },

  /* ---------------------------------------------------------------------------
     STAGE_HOSTS — the hostnames that show EVERY chain at once.

     A HOSTNAME SELECTS A SCOPE, NOT A PERSON. The apex and its aliases are the
     whole household, so they carry the combined stage; a person's own subdomain
     is that person alone and lives in their `hosts` below. The two lists must
     stay disjoint — the resolver checks this one first, so a name in both would
     quietly mean "everyone" while config.js read as though it named one person.
     The suite asserts the disjointness rather than trusting it.

     This is also the FALLBACK: a hostname in neither list gets the combined
     stage. An alternate domain name reaches the distribution the moment it is
     added, which is usually well before anyone edits this file, and until then
     it should serve everybody rather than silently serve whoever happens to be
     written first. Adding a domain is an ACM SAN in us-east-1, an alternate
     domain name on the distribution and a Route53 alias — no deploy change, and
     no edit here unless it is meant to be somebody's personal name.

     The loopback names are here on purpose: a local server is the developer
     looking at the whole composition, and it is what tools/pixel_regress.py
     photographs.
     --------------------------------------------------------------------------- */
  STAGE_HOSTS: ['wozi.com', 'www.wozi.com', 'localhost', '127.0.0.1'],

  /* ---------------------------------------------------------------------------
     PEOPLE — one entry per chain. THE ORDER MATTERS: it breaks ties when the
     chains are ordered by length, and the longest chain is the spine the rest of
     the composition is built around.

       slug    stable id, used by the ?who= override
       name    shown in the person picker
       hosts   hostnames that land on this person ALONE. One CloudFront
               distribution can carry many alternate domain names, all serving
               this same object out of s3://wozi.com — selection happens here, in
               the browser, so the HTML is byte-identical for every domain and
               one cached object serves them all. Adding a domain is an ACM SAN
               in us-east-1, an alternate domain name on the distribution, and a
               Route53 alias. No deploy change.

               These are SOLO hosts only, and must not repeat anything in
               STAGE_HOSTS: the person's own subdomain, and nothing that means
               the whole household.
       links   this person's wheels, IN TRAIN ORDER. A link is a SERVICE plus a
               HANDLE, and in the ordinary case that is the whole of it — the
               URL stem and the shape of the engraved band belong to the service
               above, not to the person.
                 slug    which service — a SERVICES key
                 handle  the account, substituted into that service's `url` and
                         `path` templates. The only personal string here.
                 href    OPTIONAL ESCAPE HATCH. Overrides the service's `url`
                         outright, and is itself run through the same `{handle}`
                         substitution — so a one-off URL still writes the handle
                         exactly once. Required for a service with no `url` of
                         its own, and the answer to any link that is simply not
                         a stem plus a handle.
                 path    OPTIONAL ESCAPE HATCH. Overrides the service's `path`
                         outright, and is taken VERBATIM — no substitution — so
                         a band can read something the URL does not contain.
                         This is what keeps Harper's band saying `harper`.

               A link that resolves to no href at all is left out of the link
               table and named in the console. Its wheel is still dealt and
               still turns, with no badge on it — the same unlinked wheel a
               missing config.js produces, rather than a badge whose empty href
               silently reloads the page.
       datum   optional. What this chain's datum plate is stamped with on a
               combined stage — the scribed reference line each chain is drawn
               against, which is how one chain is told from another. Defaults to
               `name`, verbatim, casing and all. Set it only when the plate
               should read as something other than the picker's label; it is
               never uppercased, abbreviated or given a serial, and no datum is
               drawn at all while one chain is on stage, because there is then
               nothing to tell apart. Identity deliberately does NOT live in
               colour: a person's hue preference must not reserve that hue, so
               two chains may legitimately come out looking alike.
       bridge  optional, default true. On a combined stage every chain but the
               longest is driven off it through a short run of plain idler
               wheels, which is also what sets the gap between the two. Set
               `bridge: false` and this chain is placed in the same spot with no
               drive reaching it — it becomes a machine of its own standing
               beside the others rather than one the spine turns. It has no
               effect on a page showing a single chain, because there is nothing
               to bridge to.

     THE PICKER IS HIDDEN WHILE THERE IS ONE PERSON, and hidden again whenever
     the view is deliberately one person — a personal subdomain or an explicit
     ?who=. It is a way to move around the combined stage, not a directory: a
     link to charles.wozi.com should not hand the visitor a menu of everyone else
     living on the domain.

     A word of warning before adding people: the constraint is WHEEL COUNT, not
     code. Every wheel has to fit the long axis at LINK_SHARE (0.78), so more
     wheels means smaller ones, and the centres — the hex core, the epicyclics —
     stop being legible well before the layout breaks. Two chains are
     comfortable, three is a squeeze, and beyond that a combined stage is asking
     more of the long axis than it has.
     --------------------------------------------------------------------------- */
  PEOPLE: [
    {
      slug: 'charles',
      name: 'Charles',
      hosts: ['charles.wozi.com'],
      links: [
        { slug: 'linkedin',  handle: 'csmarshall' },
        { slug: 'github',    handle: 'csmarshall' },
        /* Mastodon is retired at Charles's request — barely used. Commented
           rather than deleted, like the retired gear families: put the line
           back and the wheel returns, since SERVICES, BRAND, PILL_STACK and the
           icon are all still here. Put 'mastodon' back in SINGLES at the same
           time, or the pairing solver will not place it.

           It is also the worked example of the escape hatch: Mastodon has no
           shared stem to inherit, so the link carries the whole URL — and still
           writes the handle once, because an `href` is substituted like any
           template. The band comes from the service's `/@{handle}` as usual. */
        /* { slug: 'mastodon', handle: 'cs_marshall', href: 'http://macaw.social/@{handle}' }, */
        { slug: 'instagram', handle: 'cs_marshall' },
        { slug: 'threads',   handle: 'csmarshall' },
        { slug: 'bluesky',   handle: 'charles.wozi.com' },
        { slug: 'mail',      handle: 'charles@wozi.com' },
        { slug: 'reddit',    handle: 'cs_marshall' }
      ]
    },
    {
      slug: 'harper',
      name: 'Harper',
      /* harper.wozi.com is listed before it resolves, which costs nothing: a
         host that matches nothing simply never selects this chain, and ?who=
         reaches her either way -- and the combined stage she shares is on the
         apex regardless. Making it live is an ACM SAN in us-east-1, an alternate
         domain name on the distribution and a Route53 alias -- no deploy change,
         per the note above. */
      hosts: ['harper.wozi.com'],
      links: [
        /* HER ADDRESS IS DELIBERATELY NOT PUBLISHED YET. config.js is served to
           the web, so a handle here is public in plain text no matter what the
           band is engraved with -- a harvester reads the file, not the artwork.
           Until Charles has settled how her mail should be published, the wheel
           points at his address: the chain is complete, the badge works, and
           nothing of hers reaches the bucket. Swapping it back is this one line,
           with no code change anywhere.

           SO THE HANDLE IS HIS AND THE BAND IS HERS, and the `path` override is
           the whole reason that is expressible. Do NOT "normalise" this entry by
           deleting the override and letting the band derive from the handle: the
           band would read charles@wozi.com under her name, which is merely
           wrong -- but the obvious next tidy-up is to make the handle match the
           band, and THAT publishes her address. The two halves disagree on
           purpose. */
        { slug: 'mail', handle: 'charles@wozi.com', path: 'harper' }
      ]
    }
  ],

  /* ---------------------------------------------------------------------------
     Sibling services sit on neighbouring wheels. PAIR_SLOTS are the wheel index
     pairs that count as neighbours; PAIRS are the services to seat in them;
     SINGLES stand alone. A service named here but absent from the active
     person's links is simply skipped.
     --------------------------------------------------------------------------- */
  PAIR_SLOTS: [[0, 1], [3, 4]],
  PAIRS: [['linkedin', 'github'], ['instagram', 'threads']],
  SINGLES: ['bluesky', 'mail', 'reddit'],   /* 'mastodon' retired with its wheel */

  /* ---------------------------------------------------------------------------
     BRAND — each service's own mark colour, taken from its published brand page
     via Simple Icons (CC0). See CREDITS.md; LinkedIn's is the one hex with no
     independent cross-check, because Simple Icons does not carry LinkedIn.
     --------------------------------------------------------------------------- */
  BRAND: {
    linkedin: '#0A66C2', github: '#181717', mastodon: '#6364FF',
    instagram: '#FF0069', threads: '#000000', bluesky: '#1185FE', mail: '#E8615A',
    reddit: '#FF4500'
  },

  /* ---------------------------------------------------------------------------
     PILL_STACK — the font each service uses for its own wordmark, so the hover
     pill reads as that service's rather than as this site's. Falls back through
     to Manrope, so a face nobody has installed costs nothing. `mail` is
     deliberately empty: it is not a brand, so it uses the site's own face.
     --------------------------------------------------------------------------- */
  PILL_STACK: {
    github: "'Mona Sans', 'Segoe UI'",                    /* GitHub's own, OFL */
    linkedin: "'Brandon Text', 'Source Sans 3', 'Source Sans Pro'",
    instagram: "'Instagram Sans', 'Segoe UI'",
    threads: "'Instagram Sans', 'Segoe UI'",              /* same house as Instagram */
    bluesky: "Inter",                                     /* Bluesky's UI face, OFL */
    mastodon: "Roboto",                                   /* Mastodon's UI face, Apache */
    reddit: "'Reddit Sans', 'IBM Plex Sans'",
    mail: ""                                              /* not a brand: the site's own */
  },

  /* ---------------------------------------------------------------------------
     WHEEL_POOL — the colours wheels are dealt from.

     THE PALETTE IS AUTHORED, THE SELECTION IS COMPUTED. Five attempts at
     deriving the pool itself from a formula were all worse and it is settled:
     evenly-spaced hues are mathematically even but perceptually uneven — a
     yellow reads far lighter than a blue at the same lightness — and even
     corrected in a perceptual space the result looks *generated*. These are the
     original template's seven plus three deliberate gap-fillers, and that
     authored imbalance is what stops it reading as algorithmic.

     What IS computed is which colours appear together: dealColours() in
     index.html scores candidate sets by minimum pairwise hue distance and
     refuses neighbours closer than 40 degrees.

     Hue is DERIVED from the hex, not stored beside it. It used to be written by
     hand as an `h` field, which was a duplicate that could silently drift —
     change a colour, forget its hue, and the 40-degree rule misbehaves with no
     error. All ten agreed within one degree when checked, so deriving it was a
     no-op that removed the hazard. Adding a colour is now just adding a hex.

     Any per-theme difference belongs in the tone derivation (shades/flatTones
     in index.html), never here.
     --------------------------------------------------------------------------- */
  WHEEL_POOL: [
    '#4A90E2', '#17A05C', '#8CB8F2', '#E8615A', '#6ECFA6', '#F2C14E', '#9B8CE0',
    /* the template's seven above; three gap-fillers below */
    '#EC8C4E', '#54BFB6', '#DB79B8'
  ],

  /* ---------------------------------------------------------------------------
     ANALYTICS (#18) — cookieless, first-party, and OFF by default.

     What was here before: Google Classic Analytics on the two cards/ pages,
     with an EMPTY property id, so it never sent anything to any account. ga.js
     was shut down in 2019. It has been removed.

     How this works when enabled: a beacon is sent to a path on THIS domain —
     no third-party script, no cookie, no consent banner, nothing to load. The
     request itself is the datum, because CloudFront already writes an access
     log line for every request it serves. Counting is then an Athena query over
     logs you already pay to store, rather than a subscription.

       endpoint  path prefix to beacon, e.g. '/e'. null disables everything and
                 not one request is made.
       pageview  count page loads
       outbound  count badge clicks, as `<endpoint>/out/<service>`

     Worth knowing before switching it on:
       - Nothing serves <endpoint> yet, so these return 404. That is harmless
         and still logs, which is the whole mechanism — but it does mean 404s in
         your CloudFront metrics. A CloudFront Function returning 204 for /e/*
         would silence that, and is the tidy version of this.
       - navigator.sendBeacon survives the page being navigated away from, which
         a plain fetch on an outbound click does not.
       - Do not put anything identifying in the path. The service name is the
         point; a handle or a referrer is not.
     --------------------------------------------------------------------------- */
  ANALYTICS: {
    endpoint: null,
    pageview: true,
    outbound: true
  },

  /* ---------------------------------------------------------------------------
     ACCENTS — light value -> dark-mode counterpart. syncVars writes the accent
     onto the root element as an inline style, which beats any stylesheet rule,
     so each accent has to carry its own dark adaptation here or it loses one.
     'steel' (#5F686E) is the machine's own metal and is what ships.
     --------------------------------------------------------------------------- */
  ACCENTS: {
    '#E8483A': '#F4796D',  /* red    */
    '#3B7DE8': '#7FA9F0',  /* blue   */
    '#F4B32B': '#F7C65E',  /* amber  */
    '#1FA463': '#4FC48C',  /* green  */
    '#5F686E': '#AEB8BF'   /* steel  */
  }
};
