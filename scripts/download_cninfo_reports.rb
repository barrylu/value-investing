#!/usr/bin/env ruby

require 'json'
require 'net/http'
require 'uri'
require 'fileutils'
require 'time'

class CninfoDownloader
  QUERY_URL = URI('http://www.cninfo.com.cn/new/hisAnnouncement/query')
  STOCK_JSON_URL = URI('http://www.cninfo.com.cn/new/data/szse_stock.json')
  STATIC_BASE_URL = 'http://static.cninfo.com.cn/'
  USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36'

  COMPANY_CODE = '600900'
  COMPANY_NAME = '长江电力'
  DATE_RANGE = '2003-01-01~2025-12-31'
  OUTPUT_DIR = '/Users/luzuoguan/ai/value-investing/年报/长江电力-600900'

  EXPECTED_ANNUAL_YEARS = (2003..2024).to_a.freeze

  Query = Struct.new(:name, :categories, :searchkey, :purpose, keyword_init: true)

  def initialize
    FileUtils.mkdir_p(OUTPUT_DIR)
    @org_id = fetch_org_id
    @stock_param = "#{COMPANY_CODE},#{@org_id}"
    @seen_ids = {}
    @announcements = []
  end

  def run
    queries.each do |query|
      fetch_query(query).each { |announcement| add_announcement(announcement, query.name) }
      sleep 1
    end

    first_pass = select_relevant(@announcements)
    targeted_backfill(first_pass)
    final_set = select_relevant(@announcements)

    download_records(final_set)
    prune_extra_pdfs(final_set)
    write_metadata(final_set)
    write_download_manifest(final_set)
    write_verification_report(final_set)
  end

  private

  def queries
    [
      Query.new(
        name: 'annual',
        categories: ['category_ndbg_szsh'],
        searchkey: '',
        purpose: '年度报告'
      ),
      Query.new(
        name: 'ipo',
        categories: ['category_sf_szsh'],
        searchkey: '',
        purpose: '首发及招股材料'
      ),
      Query.new(
        name: 'correction',
        categories: ['category_bcgz_szsh'],
        searchkey: '',
        purpose: '补充更正'
      )
    ]
  end

  def fetch_org_id
    response = http_get(STOCK_JSON_URL)
    data = JSON.parse(response.body)
    stock = data.fetch('stockList').find { |item| item['code'] == COMPANY_CODE }
    raise "未找到 #{COMPANY_CODE} 的 orgId" unless stock

    stock.fetch('orgId')
  end

  def fetch_query(query)
    records = []
    page_num = 1

    loop do
      payload = {
        'pageNum' => page_num.to_s,
        'pageSize' => '30',
        'column' => 'szse',
        'tabName' => 'fulltext',
        'plate' => '',
        'stock' => @stock_param,
        'searchkey' => query.searchkey,
        'secid' => '',
        'category' => query.categories.join(';'),
        'trade' => '',
        'seDate' => DATE_RANGE,
        'sortName' => '',
        'sortType' => '',
        'isHLtitle' => 'false'
      }

      response = http_post(QUERY_URL, payload)
      data = JSON.parse(response.body)
      announcements = data['announcements'] || []
      records.concat(announcements)

      break unless data['hasMore']

      page_num += 1
      sleep 1
    end

    records
  end

  def add_announcement(announcement, source_query)
    announcement = announcement.dup
    announcement['_source_query'] = source_query
    announcement_id = announcement['announcementId'].to_s

    if announcement_id.empty?
      key = "#{announcement['announcementTime']}-#{announcement['announcementTitle']}"
      return if @seen_ids[key]

      @seen_ids[key] = true
    else
      return if @seen_ids[announcement_id]

      @seen_ids[announcement_id] = true
    end

    @announcements << announcement
  end

  def select_relevant(records)
    records.select { |announcement| relevant?(announcement) }.sort_by do |announcement|
      [announcement['announcementTime'].to_s, announcement['announcementTitle'].to_s]
    end
  end

  def relevant?(announcement)
    return false unless announcement['adjunctType'] == 'PDF'

    title = announcement['announcementTitle'].to_s
    return false if title.include?('摘要')

    case announcement['_source_query']
    when 'annual'
      annual_report_title?(title)
    when 'ipo'
      ipo_primary_title?(title)
    when 'correction'
      annual_attachment_title?(title) || ipo_attachment_title?(title)
    when 'annual_backfill'
      annual_report_title?(title) || annual_attachment_title?(title)
    when 'ipo_backfill'
      ipo_primary_title?(title) || ipo_attachment_title?(title)
    else
      false
    end
  end

  def targeted_backfill(current_records)
    missing_years(current_records).each do |year|
      backfill = Query.new(
        name: 'annual_backfill',
        categories: ['category_ndbg_szsh', 'category_bcgz_szsh'],
        searchkey: "#{year}年年度报告",
        purpose: "补查 #{year} 年年报"
      )
      fetch_query(backfill).each { |announcement| add_announcement(announcement, backfill.name) }
      sleep 1
    end

    unless current_records.any? { |item| item['announcementTitle'].to_s.match?(/招股说明书/) }
      %w[招股说明书 招股说明书附录].each do |keyword|
        backfill = Query.new(
          name: 'ipo_backfill',
          categories: ['category_sf_szsh', 'category_zj_szsh', 'category_bcgz_szsh'],
          searchkey: keyword,
          purpose: "补查 #{keyword}"
        )
        fetch_query(backfill).each { |announcement| add_announcement(announcement, backfill.name) }
        sleep 1
      end
    end
  end

  def missing_years(records)
    EXPECTED_ANNUAL_YEARS - annual_year_map(records).keys
  end

  def annual_year_map(records)
    years = {}
    records.each do |record|
      title = record['announcementTitle'].to_s
      next unless annual_report_title?(title)

      extracted = title[/((?:19|20)\d{2})年/, 1]
      next unless extracted

      year = extracted.to_i
      years[year] ||= []
      years[year] << record
    end
    years
  end

  def classify_record(record)
    title = record['announcementTitle'].to_s

    if annual_report_title?(title)
      '年报'
    elsif ipo_primary_title?(title)
      '招股及首发材料'
    elsif annual_attachment_title?(title) || ipo_attachment_title?(title)
      '附录及中介材料'
    else
      '其他相关材料'
    end
  end

  def annual_report_title?(title)
    title.match?(/年度报告/) &&
      !title.match?(/半年度|一季度|三季度|季度报告|披露日期变更|补充公告|更正公告/)
  end

  def annual_attachment_title?(title)
    title.match?(/年度报告/) &&
      title.match?(/附录|修订|更正|补充/) &&
      !title.match?(/半年度|一季度|三季度|季度报告|披露日期变更/)
  end

  def ipo_primary_title?(title)
    title.match?(/招股说明书|首次公开发行股票上市公告书/)
  end

  def ipo_attachment_title?(title)
    title.match?(/招股说明书附录|招股.*附录|招股.*补充|招股.*更正|发行保荐书|上市保荐书|律师工作报告|审计报告|资产评估报告|验资报告/)
  end

  def download_records(records)
    records.each do |record|
      url = STATIC_BASE_URL + record.fetch('adjunctUrl')
      path = file_path_for(record)
      next if File.exist?(path) && File.size?(path)

      response = http_get(URI(url), binary: true)
      File.binwrite(path, response.body)
      sleep 1
    end
  end

  def prune_extra_pdfs(records)
    expected = {}
    records.each { |record| expected[file_path_for(record)] = true }

    Dir.glob(File.join(OUTPUT_DIR, '*.pdf')).each do |path|
      File.delete(path) unless expected[path]
    end
  end

  def file_path_for(record)
    date = announcement_date(record)
    safe_title = sanitize_filename(record['announcementTitle'].to_s)
    id = record['announcementId'].to_s
    File.join(OUTPUT_DIR, "#{date}_#{safe_title}_#{id}.pdf")
  end

  def announcement_date(record)
    value = record['announcementTime']
    case value
    when Numeric
      Time.at(value / 1000).strftime('%Y-%m-%d')
    else
      value.to_s[0, 10]
    end
  end

  def sanitize_filename(name)
    cleaned = name.encode('UTF-8', invalid: :replace, undef: :replace, replace: '')
    cleaned = cleaned.gsub(/[\\\/:\*\?\"<>\|]/, '_')
    cleaned = cleaned.gsub(/\s+/, '_')
    cleaned = cleaned.gsub(/_+/, '_')
    cleaned = cleaned.sub(/\A_+/, '').sub(/_+\z/, '')
    cleaned.empty? ? 'untitled' : cleaned[0, 120]
  end

  def write_metadata(records)
    payload = records.map do |record|
      {
        id: record['announcementId'],
        title: record['announcementTitle'],
        date: announcement_date(record),
        source_query: record['_source_query'],
        kind: classify_record(record),
        url: STATIC_BASE_URL + record.fetch('adjunctUrl'),
        file: File.basename(file_path_for(record))
      }
    end

    File.write(File.join(OUTPUT_DIR, 'metadata.json'), JSON.pretty_generate(payload))
  end

  def write_download_manifest(records)
    lines = []
    lines << "# 长江电力下载清单"
    lines << ''
    lines << "- 公司：#{COMPANY_NAME}（#{COMPANY_CODE}.SH）"
    lines << "- 来源：巨潮资讯网 `hisAnnouncement/query` 与 `static.cninfo.com.cn`"
    lines << "- 生成时间：#{Time.now.strftime('%Y-%m-%d %H:%M:%S')}"
    lines << "- 文件总数：#{records.length}"
    lines << ''

    records.group_by { |record| classify_record(record) }.sort.each do |kind, items|
      lines << "## #{kind}"
      lines << ''
      items.sort_by { |record| [announcement_date(record), record['announcementTitle'].to_s] }.each do |record|
        lines << "- #{announcement_date(record)} | #{record['announcementTitle']} | `#{File.basename(file_path_for(record))}` | #{STATIC_BASE_URL + record.fetch('adjunctUrl')}"
      end
      lines << ''
    end

    File.write(File.join(OUTPUT_DIR, '下载清单.md'), lines.join("\n"))
  end

  def write_verification_report(records)
    annual_map = annual_year_map(records)
    lines = []
    lines << "# 长江电力核对结果"
    lines << ''
    lines << "- 核对时间：#{Time.now.strftime('%Y-%m-%d %H:%M:%S')}"
    lines << "- 预期年报年度：#{EXPECTED_ANNUAL_YEARS.first}-#{EXPECTED_ANNUAL_YEARS.last}"
    lines << "- 实际识别年报年度数：#{annual_map.keys.sort.length}"
    lines << ''
    lines << "## 年报年度核对"
    lines << ''

    EXPECTED_ANNUAL_YEARS.each do |year|
      items = annual_map[year] || []
      if items.empty?
        lines << "- [缺失] #{year} 年年报"
      else
        items.each do |item|
          lines << "- [已找到] #{year} 年 | #{item['announcementTitle']} | `#{File.basename(file_path_for(item))}`"
        end
      end
    end

    ipo_items = records.select { |record| classify_record(record) == '招股及首发材料' || classify_record(record) == '附录及中介材料' }
    lines << ''
    lines << "## 招股及附录核对"
    lines << ''
    if ipo_items.empty?
      lines << '- [缺失] 未识别到招股说明书或附录类材料'
    else
      ipo_items.sort_by { |record| [announcement_date(record), record['announcementTitle'].to_s] }.each do |item|
        lines << "- [已找到] #{announcement_date(item)} | #{item['announcementTitle']} | `#{File.basename(file_path_for(item))}`"
      end
    end

    missing = missing_years(records)
    lines << ''
    lines << "## 结论"
    lines << ''
    if missing.empty? && ipo_items.any? { |item| item['announcementTitle'].to_s.match?(/招股说明书/) }
      lines << '- 年报年度覆盖完整，且已识别到招股说明书相关材料。'
    else
      lines << "- 仍需人工复核的缺口：#{missing.empty? ? '无年报缺口' : missing.join(', ')}"
      lines << "- 招股材料识别状态：#{ipo_items.any? { |item| item['announcementTitle'].to_s.match?(/招股说明书/) } ? '已识别到招股说明书' : '未明确识别到招股说明书'}"
    end

    File.write(File.join(OUTPUT_DIR, '核对结果.md'), lines.join("\n"))
  end

  def http_get(uri, binary: false)
    request = Net::HTTP::Get.new(uri)
    default_headers.each { |key, value| request[key] = value }
    perform_request(uri, request, binary: binary)
  end

  def http_post(uri, form_data)
    request = Net::HTTP::Post.new(uri)
    default_headers.each { |key, value| request[key] = value }
    request.set_form_data(form_data)
    perform_request(uri, request)
  end

  def perform_request(uri, request, binary: false)
    attempts = 0
    begin
      attempts += 1
      response = Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == 'https', open_timeout: 30, read_timeout: 120) do |http|
        http.request(request)
      end
      unless response.is_a?(Net::HTTPSuccess)
        raise "HTTP #{response.code} for #{uri}"
      end

      response.body.force_encoding('ASCII-8BIT') if binary
      response
    rescue StandardError => error
      raise error if attempts >= 3

      sleep 2
      retry
    end
  end

  def default_headers
    {
      'User-Agent' => USER_AGENT,
      'Accept' => 'application/json, text/javascript, */*; q=0.01',
      'X-Requested-With' => 'XMLHttpRequest',
      'Origin' => 'http://www.cninfo.com.cn',
      'Referer' => 'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'
    }
  end
end

CninfoDownloader.new.run
