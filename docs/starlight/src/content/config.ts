import { defineCollection, z } from "astro:content";
import { docsSchema } from "@astrojs/starlight/schema";

const docs = defineCollection({
  schema: docsSchema({
    extend: z.object({
      landingPages: z.array(z.string()).default([]),
      landingAuthor: z.string().optional(),
      pubDate: z.string().optional(),
    }),
  }),
});

const reading = defineCollection({
  type: "data",
  schema: z.object({
    items: z.array(
      z.object({
        title: z.string(),
        source: z.string(),
        url: z.string().url(),
        paywalled: z.boolean().default(false),
        note: z.string().optional(),
      }),
    ),
  }),
});

export const collections = {
  docs,
  reading,
};
