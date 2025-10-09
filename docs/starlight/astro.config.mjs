import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import mdx from "@astrojs/mdx";

export default defineConfig({
  site: "https://issuesuite.io/docs",
  integrations: [
    starlight({
      title: "IssueSuite Documentation",
      favicon: "/favicon.svg",
      components: {
        Footer: "./src/components/Footer.astro",
      },
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
      social: {
        github: "https://github.com/IAmJonoBo/IssueSuite",
      },
      editLink: {
        baseUrl: "https://github.com/IAmJonoBo/IssueSuite/tree/main/docs/starlight/src/content/docs",
      },
    }),
    mdx(),
  ],
});
