"use client";

import { useEffect } from "react";

export function Motion() {
  useEffect(() => {
    const nodes = Array.from(
      document.querySelectorAll<HTMLElement>("[data-reveal]"),
    );
    const routes = Array.from(
      document.querySelectorAll<HTMLElement>("[data-route]"),
    );

    if (
      !("IntersectionObserver" in window) ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      nodes.forEach((node) => node.classList.add("in"));
      routes.forEach((node) => node.classList.add("is-drawn"));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("in");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );

    const routeObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-drawn");
          routeObserver.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.25 },
    );

    nodes.forEach((node) => observer.observe(node));
    routes.forEach((node) => routeObserver.observe(node));

    return () => {
      observer.disconnect();
      routeObserver.disconnect();
    };
  }, []);

  return null;
}
