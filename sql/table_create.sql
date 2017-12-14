/*
SQLyog  v12.2.6 (64 bit)
MySQL - 5.6.37-log : Database - micro
*********************************************************************
*/

/*!40101 SET NAMES utf8 */;

/*!40101 SET SQL_MODE=''*/;

/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
CREATE DATABASE /*!32312 IF NOT EXISTS*/`micro` /*!40100 DEFAULT CHARACTER SET utf8 */;

USE `micro`;

/*Table structure for table `zztk` */

DROP TABLE IF EXISTS `zztk`;

CREATE TABLE `zztk` (
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `selected_date` varchar(20) DEFAULT NULL,
  `selected_code` varchar(20) DEFAULT NULL,
  `buy_date` varchar(20) DEFAULT NULL,
  `buy_price` float DEFAULT NULL,
  `sell_date` varchar(20) DEFAULT NULL,
  `sell_price` float DEFAULT NULL,
  `shares` int(11) DEFAULT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8;

/*Data for the table `zztk` */

insert  into `zztk`(`ID`,`selected_date`,`selected_code`,`buy_date`,`buy_price`,`sell_date`,`sell_price`,`shares`) values 
(3,'2017-12-13','000001',NULL,NULL,NULL,NULL,0);

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
