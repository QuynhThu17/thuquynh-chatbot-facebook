const nextConfig = {
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
      {
        protocol: "https",
        hostname: "*.fbcdn.net",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "scontent-arn2-1.xx.fbcdn.net",
        pathname: "/**",
      },
    ],
  },
  experimental: {
    allowedDevOrigins: [
      "http://localhost:3002",
      "http://127.0.0.1:3002",
      "http://192.168.137.1:3002",
    ],
  } as any,
};

export default nextConfig;
