import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // distDir: ".next-dev-alt",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "mekongai-social.s3.amazonaws.com",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "*.s3.amazonaws.com",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "*.s3.us-east-1.amazonaws.com",
        pathname: "/**",
      },
    ],
  },
};

export default nextConfig;
