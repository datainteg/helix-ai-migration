import { SectionHeader } from "@/components/layout/SectionHeader";
import { Features } from "@/components/landing/Features";
import { FeatureMap } from "@/components/landing/FeatureMap";
import { ValidationRecon } from "@/components/landing/ValidationRecon";
import { DeveloperWorkspace } from "@/components/landing/DeveloperWorkspace";
import { Roadmap } from "@/components/landing/Roadmap";
import { CTA } from "@/components/landing/CTA";

export function FeaturesPage() {
  return (
    <>
      <section className="py-16 md:py-20 container-tight">
        <SectionHeader
          eyebrow="Capabilities"
          title="All features"
          description="Every capability shipped today, mapped end-to-end."
        />
      </section>
      <Features />
      <FeatureMap />
      <ValidationRecon />
      <DeveloperWorkspace />
      <Roadmap />
      <CTA />
    </>
  );
}
