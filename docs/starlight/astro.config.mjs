import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";

const DEFAULT_SITE = "https://issuesuite.io/docs";
const isGitHubPages = process.env.GITHUB_PAGES === "true";
const repository = process.env.GITHUB_REPOSITORY ?? "";
const [owner, repo] = repository.split("/");
const githubPagesSite =
  owner && repo
    ? `https://${owner.toLowerCase()}.github.io/${repo}`
    : DEFAULT_SITE;
const resolvedSite =
  process.env.DEPLOY_URL ?? (isGitHubPages ? githubPagesSite : DEFAULT_SITE);

let base;
try {
  const pathname = new URL(resolvedSite).pathname.replace(/\/$/, "");
  if (pathname && pathname !== "/") {
    base = pathname;
  }
} catch {
  base = undefined;
}

export default defineConfig({
  site: resolvedSite,
  base,
  integrations: [
    starlight({
      title: "IssueSuite Documentation",
      description:
        "Declarative GitHub Issues automation with governance-driven quality gates, deterministic sync, and observable roadmap health.",
      favicon: "/favicon.svg",
      customCss: ["./src/styles/tokens.css", "./src/styles/theme.css"],
      components: {
        Footer: "./src/components/Footer.astro",
      },
      head: [
        {
          tag: "link",
          attrs: {
            rel: "preconnect",
            href: "https://fonts.gstatic.com",
            crossorigin: "",
          },
        },
        {
          tag: "link",
          attrs: {
            rel: "stylesheet",
            href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap",
          },
        },
        {
          tag: "meta",
          attrs: {
            property: "og:image",
            content: "https://issuesuite.io/og-image.png",
          },
        },
        {
          tag: "meta",
          attrs: {
            name: "twitter:card",
            content: "summary_large_image",
          },
        },
      ],
      sidebar: [
        {
          label: "Start",
          autogenerate: { directory: "tutorials" },
        },
        {
          label: "How-to guides",
          autogenerate: { directory: "how-to" },
        },
        {
          label: "Reference",
          autogenerate: { directory: "reference" },
        },
        {
          label: "Explanations",
          autogenerate: { directory: "explanations" },
        },
      ],
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/IAmJonoBo/IssueSuite",
        },
      ],
      editLink: {
        baseUrl:
          "https://github.com/IAmJonoBo/IssueSuite/tree/main/docs/starlight/src/content/docs",
      },
    }),
    mdx(),
    sitemap(),
  ],
  redirects: {
    // Add legacy URL mappings here if needed in the future
  },
});
