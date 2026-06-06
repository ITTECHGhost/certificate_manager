-- phpMyAdmin SQL Dump
-- version 4.6.4
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: Jun 06, 2026 at 10:09 AM
-- Server version: 5.7.15-log
-- PHP Version: 5.6.26

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `certificate_manager`
--

-- --------------------------------------------------------

--
-- Table structure for table `academic_periods`
--

CREATE TABLE `academic_periods` (
  `id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `academic_year` varchar(9) NOT NULL,
  `stage_number` int(11) NOT NULL,
  `semester_num` int(5) NOT NULL DEFAULT '1',
  `study_system_id` int(11) NOT NULL DEFAULT '1'
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Table structure for table `countries`
--

CREATE TABLE `countries` (
  `id` int(11) NOT NULL,
  `name_ar` varchar(80) NOT NULL,
  `name_en` varchar(80) NOT NULL,
  `iso_code` varchar(3) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Dumping data for table `countries`
--

INSERT INTO `countries` (`id`, `name_ar`, `name_en`, `iso_code`) VALUES
(196, 'أفغانستان', 'Afghanistan', 'AF'),
(197, 'ألبانيا', 'Albania', 'AL'),
(198, 'الجزائر', 'Algeria', 'DZ'),
(199, 'أندورا', 'Andorra', 'AD'),
(200, 'أنغولا', 'Angola', 'AO'),
(201, 'أنتيغوا وباربودا', 'Antigua and Barbuda', 'AG'),
(202, 'الأرجنتين', 'Argentina', 'AR'),
(203, 'أرمينيا', 'Armenia', 'AM'),
(204, 'أستراليا', 'Australia', 'AU'),
(205, 'النمسا', 'Austria', 'AT'),
(206, 'أذربيجان', 'Azerbaijan', 'AZ'),
(207, 'جزر البهاما', 'Bahamas', 'BS'),
(208, 'البحرين', 'Bahrain', 'BH'),
(209, 'بنغلاديش', 'Bangladesh', 'BD'),
(210, 'بربادوس', 'Barbados', 'BB'),
(211, 'بيلاروسيا', 'Belarus', 'BY'),
(212, 'بلجيكا', 'Belgium', 'BE'),
(213, 'بليز', 'Belize', 'BZ'),
(214, 'بنين', 'Benin', 'BJ'),
(215, 'بوتان', 'Bhutan', 'BT'),
(216, 'بوليفيا', 'Bolivia', 'BO'),
(217, 'البوسنة والهرسك', 'Bosnia and Herzegovina', 'BA'),
(218, 'بوتسوانا', 'Botswana', 'BW'),
(219, 'البرازيل', 'Brazil', 'BR'),
(220, 'بروناي', 'Brunei', 'BN'),
(221, 'بلغاريا', 'Bulgaria', 'BG'),
(222, 'بوركينا فاسو', 'Burkina Faso', 'BF'),
(223, 'بوروندي', 'Burundi', 'BI'),
(224, 'الرأس الأخضر', 'Cape Verde', 'CV'),
(225, 'كمبوديا', 'Cambodia', 'KH'),
(226, 'الكاميرون', 'Cameroon', 'CM'),
(227, 'كندا', 'Canada', 'CA'),
(228, 'جمهورية أفريقيا الوسطى', 'Central African Republic', 'CF'),
(229, 'تشاد', 'Chad', 'TD'),
(230, 'تشيلي', 'Chile', 'CL'),
(231, 'الصين', 'China', 'CN'),
(232, 'كولومبيا', 'Colombia', 'CO'),
(233, 'جزر القمر', 'Comoros', 'KM'),
(234, 'جمهورية الكونغو', 'Republic of the Congo', 'CG'),
(235, 'جمهورية الكونغو الديمقراطية', 'Democratic Republic of the Congo', 'CD'),
(236, 'كوستاريكا', 'Costa Rica', 'CR'),
(237, 'كرواتيا', 'Croatia', 'HR'),
(238, 'كوبا', 'Cuba', 'CU'),
(239, 'قبرص', 'Cyprus', 'CY'),
(240, 'جمهورية التشيك', 'Czech Republic', 'CZ'),
(241, 'الدنمارك', 'Denmark', 'DK'),
(242, 'جيبوتي', 'Djibouti', 'DJ'),
(243, 'دومينيكا', 'Dominica', 'DM'),
(244, 'جمهورية الدومينيكان', 'Dominican Republic', 'DO'),
(245, 'الإكوادور', 'Ecuador', 'EC'),
(246, 'مصر', 'Egypt', 'EG'),
(247, 'السلفادور', 'El Salvador', 'SV'),
(248, 'غينيا الاستوائية', 'Equatorial Guinea', 'GQ'),
(249, 'إريتريا', 'Eritrea', 'ER'),
(250, 'إستونيا', 'Estonia', 'EE'),
(251, 'إسواتيني', 'Eswatini', 'SZ'),
(252, 'إثيوبيا', 'Ethiopia', 'ET'),
(253, 'فيجي', 'Fiji', 'FJ'),
(254, 'فنلندا', 'Finland', 'FI'),
(255, 'فرنسا', 'France', 'FR'),
(256, 'الغابون', 'Gabon', 'GA'),
(257, 'غامبيا', 'Gambia', 'GM'),
(258, 'جورجيا', 'Georgia', 'GE'),
(259, 'ألمانيا', 'Germany', 'DE'),
(260, 'غانا', 'Ghana', 'GH'),
(261, 'اليونان', 'Greece', 'GR'),
(262, 'غرينادا', 'Grenada', 'GD'),
(263, 'غواتيمالا', 'Guatemala', 'GT'),
(264, 'غينيا', 'Guinea', 'GN'),
(265, 'غينيا بيساو', 'Guinea-Bissau', 'GW'),
(266, 'غيانا', 'Guyana', 'GY'),
(267, 'هايتي', 'Haiti', 'HT'),
(268, 'هندوراس', 'Honduras', 'HN'),
(269, 'هنغاريا', 'Hungary', 'HU'),
(270, 'آيسلندا', 'Iceland', 'IS'),
(271, 'الهند', 'India', 'IN'),
(272, 'إندونيسيا', 'Indonesia', 'ID'),
(273, 'إيران', 'Iran', 'IR'),
(274, 'العراق', 'Iraq', 'IQ'),
(275, 'أيرلندا', 'Ireland', 'IE'),
(276, 'إسرائيل', 'Israel', 'IL'),
(277, 'إيطاليا', 'Italy', 'IT'),
(278, 'جامايكا', 'Jamaica', 'JM'),
(279, 'اليابان', 'Japan', 'JP'),
(280, 'الأردن', 'Jordan', 'JO'),
(281, 'كازاخستان', 'Kazakhstan', 'KZ'),
(282, 'كينيا', 'Kenya', 'KE'),
(283, 'كيريباتي', 'Kiribati', 'KI'),
(284, 'كوريا الشمالية', 'North Korea', 'KP'),
(285, 'كوريا الجنوبية', 'South Korea', 'KR'),
(286, 'الكويت', 'Kuwait', 'KW'),
(287, 'قيرغيزستان', 'Kyrgyzstan', 'KG'),
(288, 'لاوس', 'Laos', 'LA'),
(289, 'لاتفيا', 'Latvia', 'LV'),
(290, 'لبنان', 'Lebanon', 'LB'),
(291, 'ليسوتو', 'Lesotho', 'LS'),
(292, 'ليبيريا', 'Liberia', 'LR'),
(293, 'ليبيا', 'Libya', 'LY'),
(294, 'ليختنشتاين', 'Liechtenstein', 'LI'),
(295, 'ليتوانيا', 'Lithuania', 'LT'),
(296, 'لوكسمبورغ', 'Luxembourg', 'LU'),
(297, 'مدغشقر', 'Madagascar', 'MG'),
(298, 'مالاوي', 'Malawi', 'MW'),
(299, 'ماليزيا', 'Malaysia', 'MY'),
(300, 'جزر المالديف', 'Maldives', 'MV'),
(301, 'مالي', 'Mali', 'ML'),
(302, 'مالطا', 'Malta', 'MT'),
(303, 'جزر مارشال', 'Marshall Islands', 'MH'),
(304, 'موريتانيا', 'Mauritania', 'MR'),
(305, 'موريشيوس', 'Mauritius', 'MU'),
(306, 'المكسيك', 'Mexico', 'MX'),
(307, 'ميكرونيزيا', 'Micronesia', 'FM'),
(308, 'مولدوفا', 'Moldova', 'MD'),
(309, 'موناكو', 'Monaco', 'MC'),
(310, 'منغوليا', 'Mongolia', 'MN'),
(311, 'الجبل الأسود', 'Montenegro', 'ME'),
(312, 'المغرب', 'Morocco', 'MA'),
(313, 'موزمبيق', 'Mozambique', 'MZ'),
(314, 'ميانمار', 'Myanmar', 'MM'),
(315, 'ناميبيا', 'Namibia', 'NA'),
(316, 'ناورو', 'Nauru', 'NR'),
(317, 'نيبال', 'Nepal', 'NP'),
(318, 'هولندا', 'Netherlands', 'NL'),
(319, 'نيوزيلندا', 'New Zealand', 'NZ'),
(320, 'نيكاراغوا', 'Nicaragua', 'NI'),
(321, 'النيجر', 'Niger', 'NE'),
(322, 'نيجيريا', 'Nigeria', 'NG'),
(323, 'مقدونيا الشمالية', 'North Macedonia', 'MK'),
(324, 'النرويج', 'Norway', 'NO'),
(325, 'عُمان', 'Oman', 'OM'),
(326, 'باكستان', 'Pakistan', 'PK'),
(327, 'بالاو', 'Palau', 'PW'),
(328, 'فلسطين', 'Palestine', 'PS'),
(329, 'بنما', 'Panama', 'PA'),
(330, 'بابوا غينيا الجديدة', 'Papua New Guinea', 'PG'),
(331, 'باراغواي', 'Paraguay', 'PY'),
(332, 'بيرو', 'Peru', 'PE'),
(333, 'الفلبين', 'Philippines', 'PH'),
(334, 'بولندا', 'Poland', 'PL'),
(335, 'البرتغال', 'Portugal', 'PT'),
(336, 'قطر', 'Qatar', 'QA'),
(337, 'رومانيا', 'Romania', 'RO'),
(338, 'روسيا', 'Russia', 'RU'),
(339, 'رواندا', 'Rwanda', 'RW'),
(340, 'سانت كيتس ونيفيس', 'Saint Kitts and Nevis', 'KN'),
(341, 'سانت لوسيا', 'Saint Lucia', 'LC'),
(342, 'سانت فنسنت وجزر غرينادين', 'Saint Vincent and the Grenadines', 'VC'),
(343, 'ساموا', 'Samoa', 'WS'),
(344, 'سان مارينو', 'San Marino', 'SM'),
(345, 'ساو تومي وبرينسيبي', 'Sao Tome and Principe', 'ST'),
(346, 'المملكة العربية السعودية', 'Saudi Arabia', 'SA'),
(347, 'السنغال', 'Senegal', 'SN'),
(348, 'صربيا', 'Serbia', 'RS'),
(349, 'سيشل', 'Seychelles', 'SC'),
(350, 'سيراليون', 'Sierra Leone', 'SL'),
(351, 'سنغافورة', 'Singapore', 'SG'),
(352, 'سلوفاكيا', 'Slovakia', 'SK'),
(353, 'سلوفينيا', 'Slovenia', 'SI'),
(354, 'جزر سليمان', 'Solomon Islands', 'SB'),
(355, 'الصومال', 'Somalia', 'SO'),
(356, 'جنوب أفريقيا', 'South Africa', 'ZA'),
(357, 'جنوب السودان', 'South Sudan', 'SS'),
(358, 'إسبانيا', 'Spain', 'ES'),
(359, 'سريلانكا', 'Sri Lanka', 'LK'),
(360, 'السودان', 'Sudan', 'SD'),
(361, 'سورينام', 'Suriname', 'SR'),
(362, 'السويد', 'Sweden', 'SE'),
(363, 'سويسرا', 'Switzerland', 'CH'),
(364, 'سوريا', 'Syria', 'SY'),
(365, 'طاجيكستان', 'Tajikistan', 'TJ'),
(366, 'تنزانيا', 'Tanzania', 'TZ'),
(367, 'تايلاند', 'Thailand', 'TH'),
(368, 'تيمور الشرقية', 'Timor-Leste', 'TL'),
(369, 'توغو', 'Togo', 'TG'),
(370, 'تونغا', 'Tonga', 'TO'),
(371, 'ترينيداد وتوباغو', 'Trinidad and Tobago', 'TT'),
(372, 'تونس', 'Tunisia', 'TN'),
(373, 'تركيا', 'Turkey', 'TR'),
(374, 'تركمانستان', 'Turkmenistan', 'TM'),
(375, 'توفالو', 'Tuvalu', 'TV'),
(376, 'أوغندا', 'Uganda', 'UG'),
(377, 'أوكرانيا', 'Ukraine', 'UA'),
(378, 'الإمارات العربية المتحدة', 'United Arab Emirates', 'AE'),
(379, 'المملكة المتحدة', 'United Kingdom', 'GB'),
(380, 'الولايات المتحدة الأمريكية', 'United States', 'US'),
(381, 'أوروغواي', 'Uruguay', 'UY'),
(382, 'أوزبكستان', 'Uzbekistan', 'UZ'),
(383, 'فانواتو', 'Vanuatu', 'VU'),
(384, 'الفاتيكان', 'Vatican City', 'VA'),
(385, 'فنزويلا', 'Venezuela', 'VE'),
(386, 'فيتنام', 'Vietnam', 'VN'),
(387, 'اليمن', 'Yemen', 'YE'),
(388, 'زامبيا', 'Zambia', 'ZM'),
(389, 'زيمبابوي', 'Zimbabwe', 'ZW'),
(390, 'كوسوفو', 'Kosovo', 'XK');

-- --------------------------------------------------------

--
-- Table structure for table `courses`
--

CREATE TABLE `courses` (
  `id` int(11) NOT NULL,
  `name_ar` varchar(100) NOT NULL,
  `name_en` varchar(100) NOT NULL,
  `credit_hours` int(11) NOT NULL,
  `department_id` int(11) DEFAULT NULL,
  `stage_number` int(11) NOT NULL,
  `study_system_id` int(11) NOT NULL DEFAULT '1',
  `is_shared` tinyint(1) NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Table structure for table `course_departments`
--

CREATE TABLE `course_departments` (
  `course_id` int(11) NOT NULL,
  `department_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `departments`
--

CREATE TABLE `departments` (
  `id` int(11) NOT NULL,
  `name_ar` varchar(100) NOT NULL,
  `name_en` varchar(100) NOT NULL,
  `university_settings_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Table structure for table `enrollments`
--

CREATE TABLE `enrollments` (
  `id` int(11) NOT NULL,
  `period_id` int(11) NOT NULL,
  `course_id` int(11) NOT NULL,
  `score` float(3,1) NOT NULL,
  `passed_round` enum('1','2','3') NOT NULL DEFAULT '1'
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Table structure for table `governorates`
--

CREATE TABLE `governorates` (
  `id` int(11) NOT NULL,
  `name_ar` varchar(40) NOT NULL,
  `name_en` varchar(40) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Dumping data for table `governorates`
--

INSERT INTO `governorates` (`id`, `name_ar`, `name_en`) VALUES
(1, 'بغداد', 'Baghdad'),
(2, 'البصرة', 'Basra'),
(3, 'نينوى', 'Nineveh'),
(4, 'أربيل', 'Erbil'),
(5, 'النجف', 'Najaf'),
(6, 'كربلاء', 'Karbala'),
(7, 'الأنبار', 'Anbar'),
(8, 'ذي قار', 'Dhi Qar'),
(9, 'ميسان', 'Maysan'),
(10, 'واسط', 'Wasit'),
(11, 'بابل', 'Babylon'),
(12, 'ديالى', 'Diyala'),
(13, 'صلاح الدين', 'Saladin'),
(14, 'كركوك', 'Kirkuk'),
(15, 'المثنى', 'Muthanna'),
(16, 'القادسية', 'Al-Qadisiyyah'),
(17, 'السليمانية', 'Sulaymaniyah'),
(18, 'دهوك', 'Dohuk');

-- --------------------------------------------------------

--
-- Table structure for table `graduation_orders`
--

CREATE TABLE `graduation_orders` (
  `id` int(11) NOT NULL,
  `order_number` varchar(60) NOT NULL,
  `order_date` date NOT NULL,
  `department_id` int(11) NOT NULL,
  `graduation_semester` enum('first','second','summer') NOT NULL,
  `num_students` int(11) DEFAULT NULL,
  `admission_year` int(11) DEFAULT NULL,
  `study_system_id` int(11) NOT NULL,
  `notes` varchar(255) DEFAULT NULL,
  `study_type` varchar(50) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Dumping data for table `graduation_orders`
--

INSERT INTO `graduation_orders` (`id`, `order_number`, `order_date`, `department_id`, `graduation_semester`, `num_students`, `admission_year`, `study_system_id`, `notes`, `study_type`) VALUES
(253, '18515/13/2', '2018-08-07', 9, 'second', 10, 2017, 0, NULL, 'morning'),
(254, '18515/13/2', '2018-08-07', 10, 'second', 14, 2017, 0, NULL, 'morning'),
(255, '1921/13/3', '2019-01-27', 10, 'first', 3, 2017, 0, NULL, 'morning'),
(256, '7580/13/3', '2019-04-01', 9, 'first', 10, 2018, 0, NULL, 'morning'),
(257, '7580/13/3', '2019-04-01', 10, 'first', 10, 2018, 0, NULL, 'morning'),
(258, '20326/13/3', '2019-09-03', 9, 'second', 20, 2018, 0, NULL, 'morning'),
(259, '20326/13/3', '2019-09-03', 10, 'second', 39, 2018, 0, NULL, 'morning'),
(260, '15710/13/3', '2020-11-17', 9, 'first', 29, 2019, 0, NULL, 'morning'),
(262, '15710/13/3', '2020-11-17', 9, 'second', 8, 2019, 0, NULL, 'morning'),
(263, '15710/13/3', '2020-11-17', 10, 'second', 1, 2019, 0, NULL, 'morning'),
(264, '15710/13/3', '2020-11-17', 10, 'first', 53, 2019, 0, NULL, 'morning'),
(267, '24969/13/3', '2021-12-06', 9, 'first', 109, 2020, 0, NULL, 'morning'),
(268, '24969/13/3', '2021-12-06', 10, 'first', 57, 2020, 0, NULL, 'morning'),
(269, '24968/13/3', '2021-12-06', 9, 'second', 11, 2020, 0, NULL, 'morning'),
(270, '24968/13/3', '2021-12-06', 10, 'second', 47, 2020, 0, NULL, 'morning'),
(271, '18328/13/3', '2021-09-14', 9, 'first', 4, 2020, 0, NULL, 'morning'),
(272, '18328/13/3', '2021-09-14', 10, 'first', 1, 2020, 0, NULL, 'morning'),
(273, '24965/13/3', '2021-12-06', 9, 'second', 2, 2020, 0, NULL, 'morning'),
(274, '24967/13/3', '2021-12-06', 9, 'first', 21, 2020, 0, NULL, 'evening'),
(275, '24967/13/3', '2021-12-06', 10, 'first', 9, 2020, 0, NULL, 'evening'),
(276, '24966/13/3', '2021-12-06', 9, 'second', 10, 2020, 0, NULL, 'evening'),
(277, '24966/13/3', '2021-12-06', 10, 'second', 15, 2020, 0, NULL, 'evening'),
(278, '18429/13/3', '2022-08-15', 9, 'first', 1, 2021, 0, NULL, 'morning'),
(279, '18529/13/3', '2022-08-15', 10, 'first', 2, 2021, 0, NULL, 'morning'),
(280, '18428/13/3', '2022-08-15', 9, 'second', 1, 2021, 0, NULL, 'morning'),
(281, '18428/13/3', '2022-08-15', 10, 'second', 1, 2021, 0, NULL, 'morning'),
(282, '18427/13/3', '2022-08-15', 9, 'first', 109, 2021, 0, NULL, 'morning'),
(283, '18427/13/3', '2022-08-15', 10, 'first', 74, 2021, 0, NULL, 'morning'),
(284, '25617/13/3', '2022-11-10', 9, 'second', 44, 2021, 0, NULL, 'morning'),
(285, '25617/13/3', '2022-11-10', 10, 'second', 51, 2021, 0, NULL, 'morning'),
(286, '18426/13/3', '2022-08-15', 9, 'first', 35, 2021, 0, NULL, 'evening'),
(287, '18426/13/3', '2022-08-15', 10, 'first', 13, 2021, 0, NULL, 'evening'),
(288, '25618/13/3', '2022-11-10', 9, 'second', 17, 2021, 0, NULL, 'evening'),
(289, '25618/13/3', '2022-11-10', 10, 'second', 37, 2021, 0, NULL, 'evening'),
(290, '22397/13/3', '2023-09-11', 10, 'first', 35, 2022, 0, NULL, 'morning'),
(291, '22397/13/3', '2023-09-11', 9, 'first', 88, 2022, 0, NULL, 'morning'),
(292, '22396/13/3', '2023-09-11', 10, 'first', 16, 2022, 0, NULL, 'evening'),
(293, '22396/13/3', '2023-09-11', 9, 'first', 28, 2022, 0, NULL, 'evening'),
(294, '30711/13/3', '2023-11-22', 10, 'second', 39, 2022, 0, NULL, 'morning'),
(295, '30711/13/3', '2023-11-22', 9, 'second', 30, 2022, 0, NULL, 'morning'),
(296, '30712/13/3', '2023-11-22', 10, 'second', 11, 2022, 0, NULL, 'evening'),
(297, '30712/13/3', '2023-11-22', 9, 'second', 17, 2022, 0, NULL, 'evening'),
(299, '17862/13/3', '2024-07-25', 9, 'first', 31, 2023, 0, NULL, 'evening'),
(300, '17861/13/3', '2024-07-25', 10, 'first', 108, 2023, 0, NULL, 'morning'),
(301, '24124/13/3', '2024-10-16', 9, 'first', 138, 2023, 0, NULL, 'morning'),
(302, '17862/13/3', '2024-07-25', 10, 'first', 20, 2023, 0, NULL, 'evening'),
(303, '24970/13/3', '2024-10-27', 9, 'second', 36, 2023, 0, NULL, 'evening'),
(304, '24970/13/3', '2024-10-27', 10, 'second', 30, 2023, 0, NULL, 'evening'),
(305, '24969/13/3', '2024-10-27', 9, 'second', 43, 2023, 0, NULL, 'morning'),
(306, '24969/13/3', '2024-10-27', 10, 'second', 56, 2023, 0, NULL, 'morning'),
(307, '31814/13/3', '2019-12-31', 9, 'first', 10, 2018, 0, NULL, 'morning'),
(308, '16440/13/3', '2025-07-23', 9, 'first', 93, 2024, 0, NULL, 'morning'),
(309, '16440/13/3', '2025-07-23', 10, 'first', 140, 2024, 0, NULL, 'morning'),
(310, '16441/13/3', '2025-07-23', 9, 'first', 47, 2024, 0, NULL, 'evening'),
(311, '16441/13/3', '2025-07-23', 10, 'first', 39, 2024, 0, NULL, 'evening'),
(312, '23150/13/3', '2025-10-13', 10, 'second', 12, 2024, 0, NULL, 'evening'),
(313, '23150/13/3', '2025-10-13', 9, 'second', 17, 2024, 0, NULL, 'evening'),
(314, '23149/13/3', '2025-10-13', 9, 'second', 76, 2024, 0, NULL, 'morning'),
(315, '23149/13/3', '2025-10-13', 10, 'second', 21, 2024, 0, NULL, 'morning');

-- --------------------------------------------------------

--
-- Table structure for table `personnel`
--

CREATE TABLE `personnel` (
  `id` int(11) NOT NULL,
  `name_ar` varchar(80) NOT NULL,
  `name_en` varchar(80) NOT NULL,
  `academic_title_ar` varchar(50) NOT NULL,
  `academic_title_en` varchar(50) NOT NULL,
  `responsibility_ar` varchar(120) NOT NULL,
  `responsibility_en` varchar(120) NOT NULL,
  `display_order` int(11) NOT NULL DEFAULT '0',
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `personnel_role` enum('admin','user') NOT NULL DEFAULT 'user',
  `settings_id` int(11) DEFAULT '1',
  `university_settings_id` int(11) DEFAULT '1',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `personnel`
--

INSERT INTO `personnel` (`id`, `name_ar`, `name_en`, `academic_title_ar`, `academic_title_en`, `responsibility_ar`, `responsibility_en`, `display_order`, `username`, `password_hash`, `personnel_role`, `settings_id`, `university_settings_id`, `is_active`, `created_at`) VALUES
(1, 'مدير النظام', 'System Admin', 'المبرمج', 'Programmer', 'إدارة التقنية', 'IT Admin', 0, '1', '1', 'admin', NULL, NULL, 1, '2026-05-04 11:19:32'),
(2, 'صادق ابراهيم', '', '', '', '', '', 0, 'sadiq', 'sadiq1997', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(3, 'قاسم باسل', '', '', '', '', '', 0, 'qassim', 'qassim1234', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(4, 'علي شوقي', '', '', '', '', '', 0, 'ali', 'ali1997', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(5, 'اسراء', '', '', '', '', '', 0, 'exp', 'exp12345', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(6, 'زهراء عبدالكريم', '', '', '', '', '', 0, 'zahraa', 'zahraa1997', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(7, 'رائدة سالم خضير', 'Raidah S. Khudhair', 'الأستاذ الدكتور', 'Prof. Dr.', 'معاون العميد للشوون العلمية والدراسات العليا', 'Dean Assistant for Scientific Affairs and Postgraduate ', 1, 'signer_16', 'disabled', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(8, 'أسراء فاضل عبد', 'Israa F. Abed', ' ', ' ', 'مسؤول وحدة الوثائق', 'Graduate Officer', 2, 'signer_17', 'disabled', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(9, 'نغم باسل محمود', 'Nagham B. Mahmood', ' ', ' ', 'منظم الوثيقة', 'Certificate Arrangement', 3, 'signer_18', 'disabled', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(10, 'حيدر خزعل محبس', 'Haider K. Mehbes', 'الأستاذ المساعد', 'Asst. Prof. Dr.', 'مساعد رئيس الجامعة للشؤون العلمية', 'Vice Chancellor for Scientific Affairs', 4, 'signer_19', 'disabled', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(11, 'هشام كاظم هاشم', 'Husham K. Hashim', 'الأستاذ الدكتور', 'Prof. Dr.', 'العميد', 'The Dean', 5, 'signer_20', 'disabled', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(12, 'مرتجى علي ساري', 'Murtaja Ali Sari', 'المدرس الدكتور', 'Professor Dr.', 'مدير التسجيل', 'Registration Manager', 6, 'signer_21', 'disabled', 'user', 1, 1, 1, '2026-05-07 09:05:35'),
(36, 'IT', '', '', '', '', '', 0, 'IT', '123', 'user', 1, 1, 1, '2026-06-02 06:00:54');

--
-- Triggers `personnel`
--
DELIMITER $$
CREATE TRIGGER `unique_signatories_insert` BEFORE INSERT ON `personnel` FOR EACH ROW BEGIN
    DECLARE existing_slot INT;
    IF NEW.display_order BETWEEN 1 AND 6 THEN
        SELECT COUNT(*) INTO existing_slot 
        FROM `certificate_manager`.`personnel` 
        WHERE `display_order` = NEW.display_order;
        
        IF existing_slot > 0 THEN
            SIGNAL SQLSTATE '45000' 
            SET MESSAGE_TEXT = 'Operation Denied: This signatory slot is already assigned.';
        END IF;
    END IF;
END
$$
DELIMITER ;
DELIMITER $$
CREATE TRIGGER `unique_signatories_update` BEFORE UPDATE ON `personnel` FOR EACH ROW BEGIN
    DECLARE existing_slot INT;
        IF NEW.display_order BETWEEN 1 AND 6 AND NEW.display_order != OLD.display_order THEN
        SELECT COUNT(*) INTO existing_slot 
        FROM `certificate_manager`.`personnel` 
        WHERE `display_order` = NEW.display_order;
        
        IF existing_slot > 0 THEN
            SIGNAL SQLSTATE '45000' 
            SET MESSAGE_TEXT = 'Operation Denied: This signatory slot is already assigned.';
        END IF;
    END IF;
END
$$
DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `settings`
--

CREATE TABLE `settings` (
  `id` int(11) NOT NULL,
  `theme` varchar(20) DEFAULT 'System',
  `accent_color` varchar(20) DEFAULT 'blue',
  `font_family` varchar(100) DEFAULT 'Arial',
  `font_size_base` int(11) DEFAULT '13',
  `is_arabic_rtl` tinyint(1) NOT NULL DEFAULT '1'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `settings`
--

INSERT INTO `settings` (`id`, `theme`, `accent_color`, `font_family`, `font_size_base`, `is_arabic_rtl`) VALUES
(1, 'System', 'blue', 'Arial', 13, 1);

-- --------------------------------------------------------

--
-- Table structure for table `students`
--

CREATE TABLE `students` (
  `id` int(11) NOT NULL,
  `full_name_ar` varchar(150) NOT NULL,
  `full_name_en` varchar(150) NOT NULL,
  `gender` enum('M','F') NOT NULL DEFAULT 'M',
  `sequence_number` int(11) DEFAULT NULL COMMENT 'each student has their own number in case it was different from the uni_orders',
  `postgraduation_number` int(11) DEFAULT NULL COMMENT 'each student has their own number in case it was different from the uni_orders',
  `date_of_birth` date DEFAULT NULL,
  `birthplace_id` int(11) DEFAULT '1',
  `birthplace_other` varchar(100) DEFAULT NULL,
  `nationality_id` int(11) NOT NULL DEFAULT '1',
  `department_id` int(11) NOT NULL,
  `study_system_id` int(11) NOT NULL,
  `degree_level` enum('Higher Diploma','Master','PhD','Bachelor') NOT NULL DEFAULT 'Bachelor',
  `order_id` int(11) DEFAULT NULL,
  `admission_year` varchar(9) DEFAULT NULL,
  `summer_training_data` varchar(20) DEFAULT NULL,
  `average` float DEFAULT NULL,
  `graduation_date` date DEFAULT NULL,
  `graduation_semester` varchar(50) DEFAULT NULL,
  `postgraduation_no` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Table structure for table `student_supervisors`
--

CREATE TABLE `student_supervisors` (
  `id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `personnel_id` int(11) NOT NULL,
  `supervision_role` enum('Primary Supervisor','Co-Supervisor','Committee Member') NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Table structure for table `study_systems`
--

CREATE TABLE `study_systems` (
  `id` int(11) NOT NULL,
  `name_ar` varchar(60) NOT NULL,
  `name_en` varchar(60) NOT NULL,
  `study_day_type` enum('Morning','Evening','Other') NOT NULL DEFAULT 'Morning',
  `calculation_rule` enum('annual','semester') NOT NULL DEFAULT 'annual',
  `calculation_weights` varchar(100) DEFAULT '10:20:30:40',
  `period_display` enum('year','semester') DEFAULT 'semester',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Dumping data for table `study_systems`
--

INSERT INTO `study_systems` (`id`, `name_ar`, `name_en`, `study_day_type`, `calculation_rule`, `calculation_weights`, `period_display`, `is_active`, `created_at`) VALUES
(1, 'نظام فصلي', 'Annual System', 'Morning', 'annual', '10:20:30:40', 'year', 1, '2026-05-04 11:19:32'),
(2, 'نظام مقررات', 'Semester System', 'Morning', 'semester', '10:20:30:40', 'semester', 1, '2026-05-04 11:19:32'),
(3, 'نظام فصلي', 'Annual System', 'Evening', 'annual', '10:20:30:40', 'year', 1, '2026-05-19 06:33:20'),
(4, 'نظام مقررات', 'Semester System', 'Evening', 'semester', '10:20:30:40', 'semester', 1, '2026-05-19 06:33:20');

-- --------------------------------------------------------

--
-- Table structure for table `thesis_records`
--

CREATE TABLE `thesis_records` (
  `id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `title_ar` varchar(500) NOT NULL,
  `title_en` varchar(500) NOT NULL,
  `defense_date` date DEFAULT NULL,
  `committee_decision` enum('Accepted with No Corrections','Accepted with Minor Corrections','Accepted with Major Corrections','Rejected') DEFAULT NULL,
  `final_grade` float(5,2) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Table structure for table `university_settings`
--

CREATE TABLE `university_settings` (
  `id` int(11) NOT NULL,
  `univ_name_ar` varchar(100) NOT NULL DEFAULT 'جامعة البصرة',
  `univ_name_en` varchar(100) NOT NULL DEFAULT 'University of Basrah',
  `college_name_ar` varchar(100) NOT NULL DEFAULT 'كلية علوم الحاسوب وتكنولوجيا المعلومات',
  `college_name_en` varchar(100) NOT NULL DEFAULT 'College of Computer Science and Information Technology'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `university_settings`
--

INSERT INTO `university_settings` (`id`, `univ_name_ar`, `univ_name_en`, `college_name_ar`, `college_name_en`) VALUES
(1, 'جامعة البصرة', 'University of Basrah', 'كلية علوم الحاسوب وتكنولوجيا المعلومات', 'College of Computer Science and Information Technology');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `academic_periods`
--
ALTER TABLE `academic_periods`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `student_id` (`student_id`,`stage_number`,`academic_year`);

--
-- Indexes for table `countries`
--
ALTER TABLE `countries`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `iso_code` (`iso_code`);

--
-- Indexes for table `courses`
--
ALTER TABLE `courses`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name_ar` (`name_ar`,`department_id`),
  ADD KEY `department_id` (`department_id`);

--
-- Indexes for table `course_departments`
--
ALTER TABLE `course_departments`
  ADD PRIMARY KEY (`course_id`,`department_id`),
  ADD KEY `department_id` (`department_id`);

--
-- Indexes for table `departments`
--
ALTER TABLE `departments`
  ADD PRIMARY KEY (`id`),
  ADD KEY `university_settings_id` (`university_settings_id`);

--
-- Indexes for table `enrollments`
--
ALTER TABLE `enrollments`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `period_id` (`period_id`,`course_id`),
  ADD KEY `course_id` (`course_id`);

--
-- Indexes for table `governorates`
--
ALTER TABLE `governorates`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name_ar` (`name_ar`),
  ADD UNIQUE KEY `name_en` (`name_en`);

--
-- Indexes for table `graduation_orders`
--
ALTER TABLE `graduation_orders`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `idx_unique_grad_order_final` (`order_number`,`department_id`,`study_system_id`,`graduation_semester`),
  ADD KEY `department_id` (`department_id`);

--
-- Indexes for table `personnel`
--
ALTER TABLE `personnel`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`),
  ADD KEY `fk_personal_settings` (`settings_id`),
  ADD KEY `fk_personal_univ_settings` (`university_settings_id`);

--
-- Indexes for table `settings`
--
ALTER TABLE `settings`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `students`
--
ALTER TABLE `students`
  ADD PRIMARY KEY (`id`),
  ADD KEY `birthplace_id` (`birthplace_id`),
  ADD KEY `nationality_id` (`nationality_id`),
  ADD KEY `department_id` (`department_id`),
  ADD KEY `study_system_id` (`study_system_id`),
  ADD KEY `order_id` (`order_id`);

--
-- Indexes for table `student_supervisors`
--
ALTER TABLE `student_supervisors`
  ADD PRIMARY KEY (`id`),
  ADD KEY `student_id` (`student_id`),
  ADD KEY `personnel_id` (`personnel_id`);

--
-- Indexes for table `study_systems`
--
ALTER TABLE `study_systems`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `thesis_records`
--
ALTER TABLE `thesis_records`
  ADD PRIMARY KEY (`id`),
  ADD KEY `student_id` (`student_id`);

--
-- Indexes for table `university_settings`
--
ALTER TABLE `university_settings`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `academic_periods`
--
ALTER TABLE `academic_periods`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;
--
-- AUTO_INCREMENT for table `countries`
--
ALTER TABLE `countries`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=391;
--
-- AUTO_INCREMENT for table `courses`
--
ALTER TABLE `courses`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;
--
-- AUTO_INCREMENT for table `departments`
--
ALTER TABLE `departments`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;
--
-- AUTO_INCREMENT for table `enrollments`
--
ALTER TABLE `enrollments`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;
--
-- AUTO_INCREMENT for table `governorates`
--
ALTER TABLE `governorates`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=19;
--
-- AUTO_INCREMENT for table `graduation_orders`
--
ALTER TABLE `graduation_orders`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=319;
--
-- AUTO_INCREMENT for table `personnel`
--
ALTER TABLE `personnel`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=37;
--
-- AUTO_INCREMENT for table `students`
--
ALTER TABLE `students`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;
--
-- AUTO_INCREMENT for table `student_supervisors`
--
ALTER TABLE `student_supervisors`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;
--
-- AUTO_INCREMENT for table `study_systems`
--
ALTER TABLE `study_systems`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;
--
-- AUTO_INCREMENT for table `thesis_records`
--
ALTER TABLE `thesis_records`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;
--
-- Constraints for dumped tables
--

--
-- Constraints for table `academic_periods`
--
ALTER TABLE `academic_periods`
  ADD CONSTRAINT `academic_periods_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `courses`
--
ALTER TABLE `courses`
  ADD CONSTRAINT `courses_ibfk_1` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `course_departments`
--
ALTER TABLE `course_departments`
  ADD CONSTRAINT `course_departments_ibfk_1` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `course_departments_ibfk_2` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `departments`
--
ALTER TABLE `departments`
  ADD CONSTRAINT `departments_ibfk_1` FOREIGN KEY (`university_settings_id`) REFERENCES `university_settings` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `enrollments`
--
ALTER TABLE `enrollments`
  ADD CONSTRAINT `enrollments_ibfk_1` FOREIGN KEY (`period_id`) REFERENCES `academic_periods` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `enrollments_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `graduation_orders`
--
ALTER TABLE `graduation_orders`
  ADD CONSTRAINT `graduation_orders_ibfk_1` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `personnel`
--
ALTER TABLE `personnel`
  ADD CONSTRAINT `fk_personal_settings` FOREIGN KEY (`settings_id`) REFERENCES `settings` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_personal_univ_settings` FOREIGN KEY (`university_settings_id`) REFERENCES `university_settings` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `students`
--
ALTER TABLE `students`
  ADD CONSTRAINT `students_ibfk_1` FOREIGN KEY (`birthplace_id`) REFERENCES `governorates` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `students_ibfk_2` FOREIGN KEY (`nationality_id`) REFERENCES `countries` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `students_ibfk_3` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `students_ibfk_4` FOREIGN KEY (`study_system_id`) REFERENCES `study_systems` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `students_ibfk_5` FOREIGN KEY (`order_id`) REFERENCES `graduation_orders` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;

--
-- Constraints for table `student_supervisors`
--
ALTER TABLE `student_supervisors`
  ADD CONSTRAINT `student_supervisors_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `student_supervisors_ibfk_2` FOREIGN KEY (`personnel_id`) REFERENCES `personnel` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `thesis_records`
--
ALTER TABLE `thesis_records`
  ADD CONSTRAINT `thesis_records_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
