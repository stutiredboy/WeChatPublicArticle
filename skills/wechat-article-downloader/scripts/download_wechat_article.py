#!/usr/bin/env python3
"""
Download WeChat public articles and save as markdown with images.

Usage:
    python3 download_wechat_article.py "https://mp.weixin.qq.com/s/example"
"""

import os
import sys
import re
import argparse
import hashlib
import time
import subprocess
from datetime import datetime
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import html2text

# Configuration
DEFAULT_OUTPUT_DIR = "/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://mp.weixin.qq.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
TIMEOUT = 10

class WeChatArticleDownloader:
    def __init__(self, url, output_dir=DEFAULT_OUTPUT_DIR, verbose=False):
        self.url = url
        self.output_dir = output_dir
        self.verbose = verbose
        self.soup = None
        self.title = None
        self.publish_date = None
        self.content_html = None
        self.images = []  # List of (original_url, local_path, filename)
        
        # Validate URL
        if not url.startswith("https://mp.weixin.qq.com"):
            raise ValueError(f"URL must start with https://mp.weixin.qq.com, got: {url}")
    
    def log(self, message):
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    
    def fetch_html(self):
        """Download HTML content."""
        self.log(f"Fetching {self.url}")
        try:
            response = requests.get(self.url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch URL: {e}")
    
    def parse_html(self, html):
        """Parse HTML and extract metadata and content."""
        self.soup = BeautifulSoup(html, 'html.parser')
        
        # Extract title
        og_title = self.soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            self.title = og_title["content"].strip()
        else:
            title_tag = self.soup.find("title")
            self.title = title_tag.text.strip() if title_tag else "Untitled Article"
        
        # Clean title for filename
        self.title_clean = self.sanitize_filename(self.title)
        
        # Extract publish date
        pub_time = self.soup.find("meta", property="article:published_time")
        if pub_time and pub_time.get("content"):
            try:
                # Parse ISO format: 2026-02-23T12:00:00.000Z
                date_str = pub_time["content"]
                if 'T' in date_str:
                    date_str = date_str.split('T')[0]
                self.publish_date = datetime.strptime(date_str, "%Y-%m-%d")
            except:
                self.publish_date = datetime.now()
        else:
            self.publish_date = datetime.now()
        
        # Extract content
        content_selectors = [
            "#js_content",
            ".rich_media_content",
            "#js_article_content",
            ".article-content",
            "div[class*='content']",
        ]
        
        for selector in content_selectors:
            self.content_html = self.soup.select_one(selector)
            if self.content_html:
                break
        
        if not self.content_html:
            raise RuntimeError("Could not find article content in HTML")
        
        # Remove unwanted elements
        for element in self.content_html.select("script, style, .reward, .ads, .qr_code"):
            element.decompose()
        
        self.log(f"Found article: {self.title}")
        self.log(f"Publish date: {self.publish_date.strftime('%Y-%m-%d')}")
    
    def sanitize_filename(self, filename):
        """Remove invalid characters from filename."""
        # Remove invalid filesystem characters
        invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
        filename = re.sub(invalid_chars, '', filename)
        # Limit length
        if len(filename) > 100:
            filename = filename[:100]
        return filename.strip()
    
    def download_image(self, img_url, images_dir):
        """Download image and return local filename."""
        try:
            # Handle lazy loading (data-src attribute)
            if not img_url or img_url.startswith('data:'):
                return None
            
            # Ensure absolute URL
            if not img_url.startswith(('http://', 'https://')):
                img_url = urljoin(self.url, img_url)
            
            # Generate filename
            parsed = urlparse(img_url)
            ext = os.path.splitext(parsed.path)[1]
            if not ext or len(ext) > 5:
                ext = '.jpg'
            
            # Use hash to avoid filename collisions
            url_hash = hashlib.md5(img_url.encode()).hexdigest()[:8]
            filename = f"{url_hash}{ext}"
            local_path = os.path.join(images_dir, filename)
            
            # Skip if already downloaded
            if os.path.exists(local_path):
                self.log(f"Image already exists: {filename}")
                return filename
            
            # Download
            self.log(f"Downloading image: {img_url}")
            response = requests.get(img_url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            
            # Save
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            self.log(f"Saved image: {filename}")
            return filename
            
        except Exception as e:
            self.log(f"Failed to download image {img_url}: {e}")
            return None
    
    def process_images(self, images_dir):
        """Find and download all images in content."""
        os.makedirs(images_dir, exist_ok=True)
        
        # Find all img tags
        img_tags = self.content_html.find_all('img')
        self.log(f"Found {len(img_tags)} image(s)")
        
        for img in img_tags:
            # Prefer data-src (lazy loading), then src
            img_url = img.get('data-src') or img.get('src')
            if not img_url:
                continue
            
            filename = self.download_image(img_url, images_dir)
            if filename:
                # Replace with relative path
                img['src'] = f"images/{filename}"
                if img.get('data-src'):
                    del img['data-src']
                self.images.append((img_url, filename))
    
    def convert_to_markdown(self):
        """Convert HTML content to markdown."""
        # Configure html2text
        h = html2text.HTML2Text()
        h.unicode_snob = True  # Preserve Unicode
        h.escape_snob = True   # Escape special chars
        h.body_width = 0       # No line wrapping
        h.single_line_break = False
        h.emphasis_mark = '*'  # Use * for emphasis
        h.strong_mark = '**'   # Use ** for strong
        
        # Get HTML string
        html_str = str(self.content_html)
        
        # Convert
        markdown = h.handle(html_str)
        
        # Clean up
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)  # Remove excessive newlines
        markdown = markdown.strip()
        
        return markdown
    
    def save_article(self):
        """Save article to file system."""
        # Determine directory structure
        year = self.publish_date.strftime("%Y")
        month = self.publish_date.strftime("%m")
        
        # Create article directory
        article_dir = os.path.join(self.output_dir, year, month, self.title_clean)
        os.makedirs(article_dir, exist_ok=True)
        
        # Create images subdirectory
        images_dir = os.path.join(article_dir, "images")
        
        # Process images
        self.process_images(images_dir)
        
        # Convert to markdown
        markdown = self.convert_to_markdown()
        
        # Add frontmatter
        frontmatter = f"""---
title: {self.title}
date: {self.publish_date.strftime('%Y-%m-%d')}
source: {self.url}
images: {len(self.images)}
---
"""
        full_markdown = frontmatter + "\n" + markdown
        
        # Save markdown file
        md_filename = f"{self.title_clean}.md"
        md_path = os.path.join(article_dir, md_filename)
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(full_markdown)
        
        self.log(f"Saved article to: {md_path}")
        return md_path
    
    def git_commit_and_push(self, file_path):
        """Commit the downloaded article to git and push to remote."""
        try:
            # Ensure we're in the git repository root
            repo_root = self.output_dir
            if not os.path.exists(os.path.join(repo_root, '.git')):
                self.log("Not a git repository, skipping git commit/push")
                return False
            
            # Configure git user if not already configured
            try:
                subprocess.run(['git', 'config', 'user.email'], 
                             cwd=repo_root, capture_output=True, check=True)
            except subprocess.CalledProcessError:
                # Set git config locally
                subprocess.run(['git', 'config', 'user.email', 'wechat-downloader@example.com'], 
                             cwd=repo_root, check=True)
                subprocess.run(['git', 'config', 'user.name', 'WeChat Article Downloader'], 
                             cwd=repo_root, check=True)
            
            # Get relative path from repo root
            rel_path = os.path.relpath(file_path, repo_root)
            article_dir = os.path.dirname(file_path)
            rel_article_dir = os.path.relpath(article_dir, repo_root)
            
            # Add the article directory (including images)
            self.log(f"Adding to git: {rel_article_dir}")
            add_result = subprocess.run(['git', 'add', rel_article_dir], 
                                       cwd=repo_root, capture_output=True, text=True)
            if add_result.returncode != 0:
                self.log(f"git add failed: {add_result.stderr}")
                return False
            
            # Check if there are any changes to commit
            status_result = subprocess.run(['git', 'status', '--porcelain'], 
                                         cwd=repo_root, capture_output=True, text=True)
            if not status_result.stdout.strip():
                self.log("No changes to commit")
                return True
            
            # Commit with descriptive message
            commit_msg = f"Add WeChat article: {self.title}"
            self.log(f"Committing: {commit_msg}")
            commit_result = subprocess.run(['git', 'commit', '-m', commit_msg], 
                                          cwd=repo_root, capture_output=True, text=True)
            if commit_result.returncode != 0:
                self.log(f"git commit failed: {commit_result.stderr}")
                return False
            
            # Push to remote
            self.log("Pushing to remote repository...")
            push_result = subprocess.run(['git', 'push'], 
                                        cwd=repo_root, capture_output=True, text=True)
            if push_result.returncode != 0:
                self.log(f"git push failed: {push_result.stderr}")
                # Try pulling first if push is rejected
                if "rejected" in push_result.stderr.lower():
                    self.log("Attempting to pull latest changes...")
                    pull_result = subprocess.run(['git', 'pull', '--rebase'], 
                                               cwd=repo_root, capture_output=True, text=True)
                    if pull_result.returncode == 0:
                        # Retry push after pull
                        push_result = subprocess.run(['git', 'push'], 
                                                    cwd=repo_root, capture_output=True, text=True)
                        if push_result.returncode != 0:
                            self.log(f"git push still failed after pull: {push_result.stderr}")
                            return False
                    else:
                        self.log(f"git pull failed: {pull_result.stderr}")
                        return False
            
            self.log(f"Successfully committed and pushed: {rel_path}")
            return True
            
        except Exception as e:
            self.log(f"Error in git operations: {e}")
            return False
    
    def run(self):
        """Execute full download pipeline."""
        try:
            # Step 1: Fetch HTML
            html = self.fetch_html()
            
            # Step 2: Parse HTML
            self.parse_html(html)
            
            # Step 3: Save article
            output_path = self.save_article()
            
            # Report summary
            self.log("=" * 50)
            self.log(f"Download completed successfully!")
            self.log(f"Title: {self.title}")
            self.log(f"Saved to: {output_path}")
            self.log(f"Images downloaded: {len(self.images)}")
            self.log("=" * 50)
            
            # Step 4: Git commit and push
            self.log("Starting git commit and push...")
            git_success = self.git_commit_and_push(output_path)
            if git_success:
                self.log("Git operations completed successfully")
            else:
                self.log("Git operations failed or skipped (article still saved locally)")
            
            return output_path
            
        except Exception as e:
            self.log(f"Error: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description="Download WeChat public article")
    parser.add_argument("url", help="WeChat article URL (must start with https://mp.weixin.qq.com)")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Base output directory")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    
    try:
        downloader = WeChatArticleDownloader(args.url, args.output_dir, args.verbose)
        output_path = downloader.run()
        print(f"Success: {output_path}")
        sys.exit(0)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(2)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(3)

if __name__ == "__main__":
    main()